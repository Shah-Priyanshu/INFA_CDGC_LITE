from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import ScanJob
from ..schemas import BaseModel as _PydanticBase
from ..security import get_current_user, User, require_writer
from ..audit import audit_log

import os
from celery import Celery

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestRequest(BaseModel):
    idempotency_key: str | None = None


class IngestResponse(BaseModel):
    job_id: int
    status: str


def _get_celery() -> Celery:
    broker_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    app = Celery("cdgc_lite", broker=broker_url, backend=broker_url)
    # In tests, run tasks eagerly to avoid needing Redis
    if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("CELERY_EAGER") == "1":
        app.conf.task_always_eager = True
        app.conf.task_eager_propagates = True
    return app


@router.post("/{source}/scan", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
def enqueue_scan(
    source: str,
    payload: IngestRequest | None = None,
    db: Session = Depends(get_session),
    user: User | None = Depends(require_writer),
):
    # Idempotency: if a job with same source + idempotency_key exists (any status), reuse latest
    idem = (payload.idempotency_key if payload else None)

    job = None
    if idem:
        job = (
            db.query(ScanJob)
            .filter(
                ScanJob.source == source,
                ScanJob.idempotency_key == idem,
            )
            .order_by(ScanJob.id.desc())
            .first()
        )
    if not job:
        job = ScanJob(source=source, idempotency_key=idem, status="pending")
        db.add(job)
        db.commit()
        db.refresh(job)

    # Enqueue Celery task
    celery_app = _get_celery()
    # If eager, invoke task inline to avoid needing Redis in tests/local
    if celery_app.conf.task_always_eager:
        from workers.app import run_scan as run_scan_task
        # Ensure the worker uses the same DB as this request/session (important for tests)
        try:
            bind = getattr(db, "bind", None)
            if bind is not None and getattr(bind, "url", None) is not None:
                os.environ["DATABASE_URL"] = str(bind.url)
        except Exception:
            pass
        run_scan_task.apply(args=(source, job.id)).get()
    else:
        celery_app.send_task("workers.app.run_scan", args=[source, job.id])

    # Audit log enqueue action
    try:
        audit_log(
            action="enqueue_scan",
            resource="scan_job",
            resource_id=job.id,
            user=user,
            extra={"source": source, "idempotency_key": idem},
        )
    except Exception:
        pass

    return IngestResponse(job_id=job.id, status="enqueued")


class JobOut(BaseModel):
    id: int
    source: str
    status: str
    attempts: int
    idempotency_key: str | None


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_session)):
    job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Not found")
    return JobOut(
        id=job.id,
        source=job.source,
        status=job.status,
        attempts=job.attempts,
        idempotency_key=job.idempotency_key,
    )


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    source: str | None = None,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
):
    q = db.query(ScanJob)
    if source:
        q = q.filter(ScanJob.source == source)
    q = q.order_by(ScanJob.id.desc())
    jobs = q.limit(limit).offset(offset).all()
    return [
        JobOut(
            id=j.id,
            source=j.source,
            status=j.status,
            attempts=j.attempts,
            idempotency_key=j.idempotency_key,
        )
        for j in jobs
    ]
