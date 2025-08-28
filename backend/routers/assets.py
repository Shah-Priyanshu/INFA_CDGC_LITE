from __future__ import annotations

from typing import List, Optional
from sqlalchemy import text
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Asset
from ..schemas import AssetCreate, AssetOut, AssetUpdate, AssetSearchOut
from ..security import get_current_user, User, require_writer
from ..audit import audit_log

router = APIRouter(prefix="/assets", tags=["assets"])


def _visibility_clause(model, user: User | None):
    from ..security import _is_auth_disabled
    if _is_auth_disabled() or user is None or not getattr(user, "roles", None):
        return True
    from sqlalchemy import or_, func, literal
    roles = [r.lower() for r in user.roles]
    clauses = [model.visibility.is_(None)]
    vis_expr = func.lower(literal(' ') + func.coalesce(model.visibility, '') + literal(' '))
    for r in roles:
        like = f"% {r} %"
        clauses.append(vis_expr.like(like))
    return or_(*clauses)


@router.get("/", response_model=List[AssetSearchOut])
def list_assets(
    q: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
    user: User | None = Depends(get_current_user),
):
    qry = db.query(Asset).filter(Asset.deleted_at.is_(None)).filter(_visibility_clause(Asset, user))
    if q:
        # Use Postgres FTS when available; fallback to ILIKE otherwise
        dialect = getattr(db.bind, "dialect", None)
        if dialect and dialect.name == "postgresql":
            # Select highlight with ts_headline
            qry = (
                db.query(
                    Asset,
                    text(
                        "ts_headline('simple', coalesce(asset.description,''), plainto_tsquery('simple', unaccent(:q))) AS highlight"
                    ),
                )
                .filter(Asset.deleted_at.is_(None))
                .filter(text("asset.search_vector @@ plainto_tsquery('simple', unaccent(:q))"))
                .params(q=q)
            )
        else:
            like = f"%{q}%"
            qry = qry.filter((Asset.name.ilike(like)) | (Asset.description.ilike(like)))

    results = qry.order_by(Asset.id).limit(limit).offset(offset).all()
    # Shape results to include optional highlight
    shaped = []
    for r in results:
        if isinstance(r, tuple) and len(r) == 2:
            asset, highlight_row = r[0], r[1]
            highlight = None
            try:
                # When using text() column, it's returned as scalar under key 'highlight'
                highlight = r[1]
            except Exception:
                pass
        else:
            asset = r
            highlight = None
        shaped.append(
            {
                "id": asset.id,
                "system_id": asset.system_id,
                "name": asset.name,
                "description": asset.description,
                "column_names": asset.column_names,
                "created_at": asset.created_at,
                "updated_at": asset.updated_at,
                "highlight": highlight,
            }
        )
    return shaped


@router.post("/", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
def create_asset(payload: AssetCreate, db: Session = Depends(get_session), user: User | None = Depends(require_writer)):
    obj = Asset(
        system_id=payload.system_id,
        name=payload.name,
        description=payload.description,
    visibility=payload.visibility,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    try:
        audit_log("create", "asset", obj.id, user, {"name": obj.name, "system_id": obj.system_id})
    except Exception:
        pass
    return obj


@router.get("/{asset_id}", response_model=AssetOut)
def get_asset(asset_id: int, db: Session = Depends(get_session), user: User | None = Depends(get_current_user)):
    obj = (
        db.query(Asset)
        .filter(Asset.id == asset_id, Asset.deleted_at.is_(None))
        .filter(_visibility_clause(Asset, user))
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    return obj


@router.patch("/{asset_id}", response_model=AssetOut)
def update_asset(asset_id: int, payload: AssetUpdate, db: Session = Depends(get_session), user: User | None = Depends(require_writer)):
    obj = db.query(Asset).filter(Asset.id == asset_id, Asset.deleted_at.is_(None)).first()
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
        audit_log("update", "asset", obj.id, user, {"name": obj.name})
    except Exception:
        pass
    return obj


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset_id: int, db: Session = Depends(get_session), user: User | None = Depends(require_writer)):
    obj = db.query(Asset).filter(Asset.id == asset_id, Asset.deleted_at.is_(None)).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    from datetime import datetime

    obj.deleted_at = datetime.utcnow()
    db.commit()
    try:
        audit_log("delete", "asset", obj.id, user, {"name": obj.name})
    except Exception:
        pass
    return None
