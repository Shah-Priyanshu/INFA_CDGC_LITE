import os
import json
from celery import Celery
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from connectors.base import get_connector

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/cdgc_lite")

broker_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app = Celery("cdgc_lite", broker=broker_url, backend=broker_url)

# Optional eager execution for local/test runs
if (os.getenv("CELERY_EAGER") or "").strip().lower() in ("1", "true", "yes", "on"):
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True


def _utcnow() -> datetime:
    # Use timezone-aware now then drop tzinfo to keep consistent with DB naive DateTime columns
    return datetime.now(timezone.utc).replace(tzinfo=None)

@app.task(bind=True)
def ping(self):
    return "pong"


@app.task(bind=True, max_retries=5, default_retry_delay=10)
def run_scan(self, source: str, job_id: int | None = None):
    # Minimal lifecycle bookkeeping using SQLAlchemy core session
    db_url = os.getenv("DATABASE_URL", DATABASE_URL)
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine = create_engine(db_url, connect_args=connect_args)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        if job_id:
            db.execute(
                text("UPDATE scan_job SET status='running', attempts=attempts+1, updated_at=:now WHERE id=:id"),
                {"now": _utcnow(), "id": job_id},
            )
            db.commit()

        # Run connector pipeline: discover + harvest
        connector = get_connector(source)
        # Fetch last_seen_at from job if present to do incremental harvest
        since = None
        if job_id:
            row = db.execute(text("SELECT last_seen_at FROM scan_job WHERE id=:id"), {"id": job_id}).fetchone()
            if row and row[0]:
                since = row[0]

        disc = connector.discover(last_seen_at=since)
        harv = connector.harvest(since=since)

    # Upsert discovered systems, assets, and columns
    now = _utcnow()
        # 1) Systems (unique on name)
        sys_name_to_id: dict[str, int] = {}
        sys_names = {a.get("system") for a in disc.assets if a.get("system")}
        for sname in sorted(sys_names):
            row = db.execute(
                text("SELECT id, deleted_at FROM system WHERE name=:name"),
                {"name": sname},
            ).fetchone()
            if row:
                sid, deleted_at = row[0], row[1]
                if deleted_at is not None:
                    db.execute(
                        text("UPDATE system SET deleted_at=NULL, updated_at=:now WHERE id=:id"),
                        {"now": now, "id": sid},
                    )
                sys_name_to_id[sname] = sid
            else:
                db.execute(
                    text("INSERT INTO system(name, description, created_at, updated_at) VALUES (:name, :desc, :now, :now)"),
                    {"name": sname, "desc": None, "now": now},
                )
                sid = db.execute(text("SELECT id FROM system WHERE name=:name"), {"name": sname}).fetchone()[0]
                sys_name_to_id[sname] = sid

        # 2) Assets
        asset_name_to_id: dict[tuple[int, str], int] = {}
        for a in disc.assets:
            sname = a.get("system")
            aname = a.get("name")
            if not sname or not aname:
                continue
            sid = sys_name_to_id.get(sname)
            if not sid:
                continue
            row = db.execute(
                text("SELECT id, deleted_at FROM asset WHERE system_id=:sid AND name=:name"),
                {"sid": sid, "name": aname},
            ).fetchone()
            if row:
                aid, deleted_at = row[0], row[1]
                if deleted_at is not None:
                    db.execute(
                        text("UPDATE asset SET deleted_at=NULL, updated_at=:now WHERE id=:id"),
                        {"now": now, "id": aid},
                    )
                asset_name_to_id[(sid, aname)] = aid
            else:
                db.execute(
                    text("INSERT INTO asset(system_id, name, description, created_at, updated_at) VALUES (:sid, :name, :desc, :now, :now)"),
                    {"sid": sid, "name": aname, "desc": a.get("description"), "now": now},
                )
                aid = db.execute(
                    text("SELECT id FROM asset WHERE system_id=:sid AND name=:name"),
                    {"sid": sid, "name": aname},
                ).fetchone()[0]
                asset_name_to_id[(sid, aname)] = aid

        # 3) Columns: requires asset mapping; columns entries carry asset name, we infer system by matching disc.assets
        # Build a map from asset name -> system_id from discovery set
        asset_to_system_id: dict[str, int] = {}
        for a in disc.assets:
            sname = a.get("system")
            aname = a.get("name")
            sid = sys_name_to_id.get(sname) if sname else None
            if sid and aname:
                asset_to_system_id[aname] = sid

        # Track columns per asset to refresh column_names later
        cols_by_asset_id: dict[int, set[str]] = {}
        for c in disc.columns:
            aname = c.get("asset")
            cname = c.get("name")
            if not aname or not cname:
                continue
            sid = asset_to_system_id.get(aname)
            if not sid:
                continue
            aid = asset_name_to_id.get((sid, aname))
            if not aid:
                # Create asset placeholder if missing
                db.execute(
                    text("INSERT INTO asset(system_id, name, description, created_at, updated_at) VALUES (:sid, :name, :desc, :now, :now)"),
                    {"sid": sid, "name": aname, "desc": None, "now": now},
                )
                aid = db.execute(
                    text("SELECT id FROM asset WHERE system_id=:sid AND name=:name"),
                    {"sid": sid, "name": aname},
                ).fetchone()[0]
                asset_name_to_id[(sid, aname)] = aid

            row = db.execute(
                text("SELECT id, deleted_at FROM ""column"" WHERE asset_id=:aid AND name=:name"),
                {"aid": aid, "name": cname},
            ).fetchone()
            if row:
                col_id, deleted_at = row[0], row[1]
                if deleted_at is not None:
                    db.execute(
                        text("UPDATE ""column"" SET deleted_at=NULL, updated_at=:now WHERE id=:id"),
                        {"now": now, "id": col_id},
                    )
                # Update data_type/description if provided
                db.execute(
                    text("UPDATE ""column"" SET data_type=COALESCE(:dt, data_type), description=COALESCE(:desc, description), updated_at=:now WHERE id=:id"),
                    {"dt": c.get("data_type"), "desc": c.get("description"), "now": now, "id": col_id},
                )
            else:
                db.execute(
                    text("INSERT INTO ""column""(asset_id, name, data_type, description, created_at, updated_at) VALUES (:aid, :name, :dt, :desc, :now, :now)"),
                    {"aid": aid, "name": cname, "dt": c.get("data_type"), "desc": c.get("description"), "now": now},
                )
            cols_by_asset_id.setdefault(aid, set()).add(cname)

        # 4) Refresh asset.column_names cache
        for aid, names in cols_by_asset_id.items():
            names_csv = ",".join(sorted(names))
            db.execute(
                text("UPDATE asset SET column_names=:names, updated_at=:now WHERE id=:id"),
                {"names": names_csv, "now": now, "id": aid},
            )
        db.commit()

        # Persist raw payload as JSON; SQLAlchemy JSON/JSONB will serialize Python dicts appropriately
        db.execute(
            text("INSERT INTO scan_artifact(source, payload, created_at, updated_at) VALUES (:source, :payload, :now, :now)"),
            {"source": source, "payload": json.dumps(harv.payload), "now": now},
        )
        db.commit()

        if job_id:
            # Advance last_seen_at using harvester result; fallback to now
            lsa = harv.last_seen_at or _utcnow()
            db.execute(
                text("UPDATE scan_job SET status='success', last_seen_at=:lsa, updated_at=:now WHERE id=:id"),
                {"lsa": lsa, "now": _utcnow(), "id": job_id},
            )
            db.commit()
        return {"source": source, "job_id": job_id, "at": _utcnow().isoformat()}
    except Exception as e:
        if job_id:
            db.execute(
                text("UPDATE scan_job SET status='failed', updated_at=:now WHERE id=:id"),
                {"now": _utcnow(), "id": job_id},
            )
            db.commit()
        raise e
    finally:
        db.close()
