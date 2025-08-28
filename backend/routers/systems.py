from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import System
from ..schemas import SystemCreate, SystemOut, SystemUpdate
from ..security import get_current_user, User, require_writer
from ..audit import audit_log

router = APIRouter(prefix="/systems", tags=["systems"])


def _visibility_clause(model, user: User | None):
    # When auth disabled or user unknown, show all
    from ..security import _is_auth_disabled
    if _is_auth_disabled() or user is None or not getattr(user, "roles", None):
        return True
    # visibility is NULL (public) OR any role matches tokens in visibility string
    roles = [r.lower() for r in user.roles]
    tokens = [
        f"% {r} %" for r in roles
    ]
    from sqlalchemy import or_, func, literal
    clauses = [model.visibility.is_(None)]
    # Normalize visibility by surrounding with spaces to ease LIKE matching
    vis_expr = func.lower(literal(' ') + func.coalesce(model.visibility, '') + literal(' '))
    for r in roles:
        like = f"% {r} %"
        clauses.append(vis_expr.like(like))
    return or_(*clauses)


@router.get("/", response_model=List[SystemOut])
def list_systems(
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
    user: User | None = Depends(get_current_user),
):
    return (
        db.query(System)
        .filter(System.deleted_at.is_(None))
        .filter(_visibility_clause(System, user))
        .order_by(System.id)
        .limit(limit)
        .offset(offset)
        .all()
    )


@router.post("/", response_model=SystemOut, status_code=status.HTTP_201_CREATED)
def create_system(payload: SystemCreate, db: Session = Depends(get_session), user: User | None = Depends(require_writer)):
    if db.query(System).filter(System.name == payload.name, System.deleted_at.is_(None)).first():
        raise HTTPException(status_code=409, detail="System name already exists")
    obj = System(name=payload.name, description=payload.description, visibility=payload.visibility)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    try:
        audit_log("create", "system", obj.id, user, {"name": obj.name})
    except Exception:
        pass
    return obj


@router.get("/{system_id}", response_model=SystemOut)
def get_system(system_id: int, db: Session = Depends(get_session)):
    obj = db.query(System).filter(System.id == system_id, System.deleted_at.is_(None)).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    return obj


@router.patch("/{system_id}", response_model=SystemOut)
def update_system(system_id: int, payload: SystemUpdate, db: Session = Depends(get_session), user: User | None = Depends(require_writer)):
    obj = db.query(System).filter(System.id == system_id, System.deleted_at.is_(None)).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    if payload.name is not None:
        obj.name = payload.name
    if payload.description is not None:
        obj.description = payload.description
    if getattr(payload, "visibility", None) is not None:
        obj.visibility = payload.visibility
    db.commit()
    db.refresh(obj)
    try:
        audit_log("update", "system", obj.id, user, {"name": obj.name})
    except Exception:
        pass
    return obj


@router.delete("/{system_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_system(system_id: int, db: Session = Depends(get_session), user: User | None = Depends(require_writer)):
    obj = db.query(System).filter(System.id == system_id, System.deleted_at.is_(None)).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    from datetime import datetime

    obj.deleted_at = datetime.utcnow()
    db.commit()
    try:
        audit_log("delete", "system", obj.id, user, {"name": obj.name})
    except Exception:
        pass
    return None
