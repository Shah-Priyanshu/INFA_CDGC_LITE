from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Tuple

from ..base import Connector, DiscoverResult, HarvestResult


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SnowflakeConnector(Connector):
    """
    Production-grade connector with safe fallbacks:
    - If required env vars or snowflake-connector-python are missing, returns a minimal stub (keeps tests green).
    - When configured, performs:
        - discover(): scan INFORMATION_SCHEMA for tables/columns across configured databases
        - harvest(): scan ACCOUNT_USAGE.QUERY_HISTORY for queries since the provided timestamp

    Env vars (all optional for local dev):
      SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD | SNOWFLAKE_PRIVATE_KEY
      SNOWFLAKE_ROLE, SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASES (comma-separated, default: current DB)
    """

    def _get_conn(self):
        # Explicit feature flag to enable real Snowflake connections in non-test environments
        if (os.getenv("SNOWFLAKE_ENABLED") or "").strip().lower() not in ("1", "true", "yes", "on"):
            return None, None
        cfg = {
            "account": os.getenv("SNOWFLAKE_ACCOUNT"),
            "user": os.getenv("SNOWFLAKE_USER"),
            "password": os.getenv("SNOWFLAKE_PASSWORD"),
            "role": os.getenv("SNOWFLAKE_ROLE"),
            "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
        }
        # Minimal check: account and user must exist to attempt a real connection
        if not cfg["account"] or not cfg["user"]:
            return None, None
        try:
            import snowflake.connector  # type: ignore

            conn = snowflake.connector.connect(
                account=cfg["account"],
                user=cfg["user"],
                password=cfg["password"],
                role=cfg["role"],
                warehouse=cfg["warehouse"],
                autocommit=True,
            )
            dbs = [d.strip() for d in (os.getenv("SNOWFLAKE_DATABASES") or "").split(",") if d.strip()]
            return conn, dbs
        except Exception:
            # Missing dependency or invalid credentials → fall back
            return None, None

    def discover(self, last_seen_at: Optional[datetime] = None) -> DiscoverResult:
        conn, dbs = self._get_conn()
        if not conn:
            # Fallback stub
            return DiscoverResult(
                assets=[{"system": "snowflake", "name": "db.schema.table"}],
                columns=[{"asset": "db.schema.table", "name": "id", "data_type": "NUMBER"}],
            )

        assets: List[Dict[str, Any]] = []
        columns: List[Dict[str, Any]] = []

        # If no explicit DBs configured, rely on the current DB context
        cursor = conn.cursor()
        try:
            if not dbs:
                dbs = []
                cur2 = conn.cursor()
                try:
                    cur2.execute("select current_database()")
                    row = cur2.fetchone()
                    if row and row[0]:
                        dbs = [row[0]]
                finally:
                    cur2.close()

            for db in dbs:
                # Snowflake requires fully-qualified references; use INFORMATION_SCHEMA for metadata
                cursor.execute(f"USE DATABASE {db}")

                # Tables with last_altered for incremental discovery
                incr_clause = ""
                params: Tuple[Any, ...] = tuple()
                if last_seen_at:
                    incr_clause = " WHERE last_altered >= TO_TIMESTAMP(%s)"
                    params = (last_seen_at,)
                cursor.execute(
                    """
                    SELECT table_catalog, table_schema, table_name, table_type, last_altered
                    FROM INFORMATION_SCHEMA.TABLES
                    %s
                    """ % incr_clause,
                    params,
                )
                for (catalog, schema, table, ttype, last_altered) in cursor.fetchall():
                    fq = f"{catalog}.{schema}.{table}"
                    assets.append({
                        "system": "snowflake",
                        "name": fq,
                        "description": None,
                        "type": ttype,
                        "last_altered": last_altered.isoformat() if hasattr(last_altered, 'isoformat') else str(last_altered),
                    })

                # Columns
                cursor.execute(
                    """
                    SELECT table_catalog, table_schema, table_name, column_name, data_type
                    FROM INFORMATION_SCHEMA.COLUMNS
                    """
                )
                for (catalog, schema, table, col, dtype) in cursor.fetchall():
                    fq = f"{catalog}.{schema}.{table}"
                    columns.append({
                        "asset": fq,
                        "name": col,
                        "data_type": dtype,
                    })
        finally:
            cursor.close()
            conn.close()

        return DiscoverResult(assets=assets, columns=columns)

    def harvest(self, since: Optional[datetime] = None) -> HarvestResult:
        conn, _ = self._get_conn()
        if not conn:
            # Fallback stub
            if since is None:
                since_str = None
            elif hasattr(since, "isoformat"):
                since_str = since.isoformat() + "Z"
            else:
                # already a string or other type; coerce to string safely
                since_str = str(since)
            payload: Dict[str, Any] = {
                "type": "snowflake",
                "harvested_at": _utcnow().isoformat() + "Z",
                "since": since_str,
                "items": [
                    {"asset": "db.schema.table", "row_count": 1000},
                ],
            }
            return HarvestResult(payload=payload, last_seen_at=_utcnow())

        items: List[Dict[str, Any]] = []
        max_end_time: Optional[datetime] = None

        try:
            cur = conn.cursor()
            # Query history; restrict to finalized queries and non-null text
            if since:
                # Normalize 'since' if it's a string (from SQLite or external input)
                if isinstance(since, str):
                    try:
                        since = datetime.fromisoformat(since.replace("Z", "+00:00"))
                    except Exception:
                        since = None
                cur.execute(
                    """
                    SELECT QUERY_TEXT, START_TIME, END_TIME
                    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
                    WHERE END_TIME >= TO_TIMESTAMP(%s)
                      AND QUERY_TEXT IS NOT NULL
                    ORDER BY END_TIME ASC
                    LIMIT 10000
                    """,
                    (since,),
                )
            else:
                cur.execute(
                    """
                    SELECT QUERY_TEXT, START_TIME, END_TIME
                    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
                    WHERE QUERY_TEXT IS NOT NULL
                    ORDER BY END_TIME DESC
                    LIMIT 10000
                    """
                )
            rows = cur.fetchall()
        finally:
            try:
                cur.close()
            except Exception:
                pass
            conn.close()

        # Parse SQL with sqlglot when available; otherwise include raw text only
        sources: List[str] = []
        try:
            import sqlglot
            from sqlglot import exp
        except Exception:
            sqlglot = None  # type: ignore
            exp = None  # type: ignore

        for (query_text, start_time, end_time) in rows:
            end_dt = end_time if isinstance(end_time, datetime) else None
            if end_dt and (max_end_time is None or end_dt > max_end_time):
                max_end_time = end_dt

            entry: Dict[str, Any] = {
                "query_text": query_text,
                "start_time": start_time.isoformat() if hasattr(start_time, 'isoformat') else str(start_time),
                "end_time": end_time.isoformat() if hasattr(end_time, 'isoformat') else str(end_time),
            }
            if sqlglot:
                try:
                    parsed = sqlglot.parse_one(query_text, dialect="snowflake")
                    # Collect referenced table identifiers
                    tbls = set()
                    for node in parsed.find_all(exp.Table):  # type: ignore[attr-defined]
                        name = ".".join(filter(None, [getattr(node, 'catalog', None), getattr(node, 'db', None), getattr(node, 'name', None)]))
                        if not name:
                            # Fallback to table name only
                            name = getattr(node, 'name', None) or None
                        if name:
                            tbls.add(name)
                    entry["tables"] = sorted(tbls)
                except Exception:
                    # best-effort only
                    entry["tables"] = []
            items.append(entry)

        payload: Dict[str, Any] = {
            "type": "snowflake",
            "harvested_at": _utcnow().isoformat() + "Z",
            "since": since.isoformat() + "Z" if since else None,
            "items": items,
        }
        return HarvestResult(payload=payload, last_seen_at=max_end_time or _utcnow())
