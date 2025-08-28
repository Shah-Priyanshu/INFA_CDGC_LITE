from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Asset, ColumnModel
from ..security import get_current_user, User
from sqlalchemy import or_, func, literal

router = APIRouter(prefix="/search", tags=["search"])


def _visibility_clause(model, user: User | None):
    from ..security import _is_auth_disabled
    if _is_auth_disabled() or user is None or not getattr(user, "roles", None):
        return True
    roles = [r.lower() for r in user.roles]
    clauses = [model.visibility.is_(None)]
    vis_expr = func.lower(literal(' ') + func.coalesce(model.visibility, '') + literal(' '))
    for r in roles:
        clauses.append(vis_expr.like(f"% {r} %"))
    return or_(*clauses)


@router.get("/")
def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
    user: User | None = Depends(get_current_user),
):
    dialect = getattr(db.bind, "dialect", None)
    is_pg = bool(dialect and dialect.name == "postgresql")

    results: Dict[str, List[Dict[str, Any]]] = {"assets": [], "columns": []}

    if is_pg:
        # Assets with highlight
        a_rows = (
            db.query(
                Asset,
                text(
                    "ts_headline('simple', coalesce(asset.description,''), plainto_tsquery('simple', unaccent(:q))) AS highlight"
                ),
                text(
                    "ts_rank(asset.search_vector, plainto_tsquery('simple', unaccent(:q))) as rank"
                ),
            )
            .filter(Asset.deleted_at.is_(None))
            .filter(_visibility_clause(Asset, user))
            .filter(text("asset.search_vector @@ plainto_tsquery('simple', unaccent(:q))"))
            .params(q=q)
            .order_by(text("rank DESC"), Asset.id)
            .limit(limit)
            .offset(offset)
            .all()
        )
        for a, hl, rank in a_rows:
            results["assets"].append(
                {
                    "id": a.id,
                    "system_id": a.system_id,
                    "name": a.name,
                    "description": a.description,
                    "highlight": hl,
                    "rank": float(rank) if rank is not None else None,
                }
            )

        # Columns with highlight
        c_rows = (
            db.query(
                ColumnModel,
                text(
                    "ts_headline('simple', coalesce(""column"".description,''), plainto_tsquery('simple', unaccent(:q))) AS highlight"
                ),
                text(
                    "ts_rank(""column"".search_vector, plainto_tsquery('simple', unaccent(:q))) as rank"
                ),
            )
            .join(Asset, Asset.id == ColumnModel.asset_id)
            .filter(ColumnModel.deleted_at.is_(None), Asset.deleted_at.is_(None))
            .filter(_visibility_clause(Asset, user))
            .filter(text("\"column\".search_vector @@ plainto_tsquery('simple', unaccent(:q))"))
            .params(q=q)
            .order_by(text("rank DESC"), ColumnModel.id)
            .limit(limit)
            .offset(offset)
            .all()
        )
        for c, hl, rank in c_rows:
            results["columns"].append(
                {
                    "id": c.id,
                    "asset_id": c.asset_id,
                    "name": c.name,
                    "data_type": c.data_type,
                    "description": c.description,
                    "highlight": hl,
                    "rank": float(rank) if rank is not None else None,
                }
            )
    else:
        like = f"%{q}%"
        a_rows = (
            db.query(Asset)
            .filter(Asset.deleted_at.is_(None))
            .filter(_visibility_clause(Asset, user))
            .filter((Asset.name.ilike(like)) | (Asset.description.ilike(like)))
            .order_by(Asset.id)
            .limit(limit)
            .offset(offset)
            .all()
        )
        for a in a_rows:
            results["assets"].append(
                {
                    "id": a.id,
                    "system_id": a.system_id,
                    "name": a.name,
                    "description": a.description,
                    "highlight": None,
                }
            )
        c_rows = (
            db.query(ColumnModel)
            .join(Asset, Asset.id == ColumnModel.asset_id)
            .filter(ColumnModel.deleted_at.is_(None), Asset.deleted_at.is_(None))
            .filter(_visibility_clause(Asset, user))
            .filter((ColumnModel.name.ilike(like)) | (ColumnModel.description.ilike(like)))
            .order_by(ColumnModel.id)
            .limit(limit)
            .offset(offset)
            .all()
        )
        for c in c_rows:
            results["columns"].append(
                {
                    "id": c.id,
                    "asset_id": c.asset_id,
                    "name": c.name,
                    "data_type": c.data_type,
                    "description": c.description,
                    "highlight": None,
                }
            )

    return results
