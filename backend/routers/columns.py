from __future__ import annotations

from typing import List, Optional
from sqlalchemy import text
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import ColumnModel, Asset
from ..schemas import ColumnCreate, ColumnOut, ColumnUpdate, ColumnSearchOut
from ..security import get_current_user, User, require_writer
from ..audit import audit_log

router = APIRouter(prefix="/columns", tags=["columns"])


def _visibility_clause(model, user: User | None):
    from ..security import _is_auth_disabled
    if _is_auth_disabled() or user is None or not getattr(user, "roles", None):
        return True
    from sqlalchemy import or_, func, literal
    roles = [r.lower() for r in user.roles]
    clauses = [model.visibility.is_(None)]
    vis_expr = func.lower(literal(' ') + func.coalesce(model.visibility, '') + literal(' '))
    for r in roles:
        clauses.append(vis_expr.like(f"% {r} %"))
    return or_(*clauses)


@router.get("/", response_model=List[ColumnSearchOut])
def list_columns(
    q: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
    user: User | None = Depends(get_current_user),
):
    qry = (
        db.query(ColumnModel)
        .join(Asset, Asset.id == ColumnModel.asset_id)
        .filter(ColumnModel.deleted_at.is_(None), Asset.deleted_at.is_(None))
        .filter(_visibility_clause(Asset, user))
    )
    if q:
        dialect = getattr(db.bind, "dialect", None)
        if dialect and dialect.name == "postgresql":
            qry = (
                db.query(
                    ColumnModel,
                    text(
                        "ts_headline('simple', coalesce(""column"".description,''), plainto_tsquery('simple', unaccent(:q))) AS highlight"
                    ),
                )
                .join(Asset, Asset.id == ColumnModel.asset_id)
                .filter(ColumnModel.deleted_at.is_(None), Asset.deleted_at.is_(None))
                .filter(_visibility_clause(Asset, user))
                .filter(text("\"column\".search_vector @@ plainto_tsquery('simple', unaccent(:q))"))
                .params(q=q)
            )
        else:
            like = f"%{q}%"
            qry = qry.filter((ColumnModel.name.ilike(like)) | (ColumnModel.description.ilike(like)))
    results = qry.order_by(ColumnModel.id).limit(limit).offset(offset).all()
    shaped = []
    for r in results:
        if isinstance(r, tuple) and len(r) == 2:
            col = r[0]
            highlight = r[1]
        else:
            col = r
            highlight = None
        shaped.append(
            {
                "id": col.id,
                "asset_id": col.asset_id,
                "name": col.name,
                "data_type": col.data_type,
                "description": col.description,
                "created_at": col.created_at,
                "updated_at": col.updated_at,
                "highlight": highlight,
            }
        )
    return shaped


@router.post("/", response_model=ColumnOut, status_code=status.HTTP_201_CREATED)
def create_column(payload: ColumnCreate, db: Session = Depends(get_session), user: User | None = Depends(require_writer)):
    obj = ColumnModel(
        asset_id=payload.asset_id,
        name=payload.name,
        data_type=payload.data_type,
        description=payload.description,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    # Update asset.column_names cache
    from ..models import Asset
    cols = db.query(ColumnModel.name).filter(ColumnModel.asset_id == obj.asset_id, ColumnModel.deleted_at.is_(None)).order_by(ColumnModel.name).all()
    names = ",".join([c[0] for c in cols])
    db.query(Asset).filter(Asset.id == obj.asset_id).update({"column_names": names})
    db.commit()
    try:
        audit_log("create", "column", obj.id, user, {"name": obj.name, "asset_id": obj.asset_id})
    except Exception:
        pass
    return obj


@router.get("/{column_id}", response_model=ColumnOut)
def get_column(column_id: int, db: Session = Depends(get_session), user: User | None = Depends(get_current_user)):
    obj = (
        db.query(ColumnModel)
        .join(Asset, Asset.id == ColumnModel.asset_id)
        .filter(ColumnModel.id == column_id, ColumnModel.deleted_at.is_(None), Asset.deleted_at.is_(None))
        .filter(_visibility_clause(Asset, user))
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    return obj


@router.patch("/{column_id}", response_model=ColumnOut)
def update_column(column_id: int, payload: ColumnUpdate, db: Session = Depends(get_session), user: User | None = Depends(require_writer)):
    obj = db.query(ColumnModel).filter(ColumnModel.id == column_id, ColumnModel.deleted_at.is_(None)).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    if payload.name is not None:
        obj.name = payload.name
    if payload.data_type is not None:
        obj.data_type = payload.data_type
    if payload.description is not None:
        obj.description = payload.description
    db.commit()
    db.refresh(obj)
    # Update asset.column_names cache
    from ..models import Asset
    cols = db.query(ColumnModel.name).filter(ColumnModel.asset_id == obj.asset_id, ColumnModel.deleted_at.is_(None)).order_by(ColumnModel.name).all()
    names = ",".join([c[0] for c in cols])
    db.query(Asset).filter(Asset.id == obj.asset_id).update({"column_names": names})
    db.commit()
    try:
        audit_log("update", "column", obj.id, user, {"name": obj.name})
    except Exception:
        pass
    return obj


@router.delete("/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_column(column_id: int, db: Session = Depends(get_session), user: User | None = Depends(require_writer)):
    obj = db.query(ColumnModel).filter(ColumnModel.id == column_id, ColumnModel.deleted_at.is_(None)).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    from datetime import datetime

    obj.deleted_at = datetime.utcnow()
    db.commit()
    # Update asset.column_names cache
    from ..models import Asset
    cols = db.query(ColumnModel.name).filter(ColumnModel.asset_id == obj.asset_id, ColumnModel.deleted_at.is_(None)).order_by(ColumnModel.name).all()
    names = ",".join([c[0] for c in cols])
    db.query(Asset).filter(Asset.id == obj.asset_id).update({"column_names": names})
    db.commit()
    try:
        audit_log("delete", "column", obj.id, user, {"name": obj.name})
    except Exception:
        pass
    return None
