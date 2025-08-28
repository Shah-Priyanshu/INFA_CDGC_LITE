from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import GlossaryTerm, AssetTermLink, ColumnTermLink
from pydantic import BaseModel
from ..security import get_current_user, User, require_writer
from ..audit import audit_log

router = APIRouter(prefix="/glossary", tags=["glossary"])


class GlossaryCreate(BaseModel):
    name: str
    description: str | None = None


class GlossaryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class GlossaryOut(BaseModel):
    id: int
    name: str
    description: str | None


@router.get("/", response_model=List[GlossaryOut])
def list_terms(db: Session = Depends(get_session)):
    return db.query(GlossaryTerm).filter(GlossaryTerm.deleted_at.is_(None)).all()


@router.post("/", response_model=GlossaryOut, status_code=status.HTTP_201_CREATED)
def create_term(payload: GlossaryCreate, db: Session = Depends(get_session), user: User | None = Depends(require_writer)):
    if db.query(GlossaryTerm).filter(GlossaryTerm.name == payload.name, GlossaryTerm.deleted_at.is_(None)).first():
        raise HTTPException(status_code=409, detail="Glossary term already exists")
    obj = GlossaryTerm(name=payload.name, description=payload.description)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    try:
        audit_log("create", "glossary_term", obj.id, user, {"name": obj.name})
    except Exception:
        pass
    return obj


@router.patch("/{term_id}", response_model=GlossaryOut)
def update_term(term_id: int, payload: GlossaryUpdate, db: Session = Depends(get_session), user: User | None = Depends(require_writer)):
    obj = db.query(GlossaryTerm).filter(GlossaryTerm.id == term_id, GlossaryTerm.deleted_at.is_(None)).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    if payload.name is not None:
        obj.name = payload.name
    if payload.description is not None:
        obj.description = payload.description
    db.commit()
    db.refresh(obj)
    try:
        audit_log("update", "glossary_term", obj.id, user, {"name": obj.name})
    except Exception:
        pass
    return obj


@router.delete("/{term_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_term(term_id: int, db: Session = Depends(get_session), user: User | None = Depends(require_writer)):
    obj = db.query(GlossaryTerm).filter(GlossaryTerm.id == term_id, GlossaryTerm.deleted_at.is_(None)).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    from datetime import datetime

    obj.deleted_at = datetime.utcnow()
    db.commit()
    try:
        audit_log("delete", "glossary_term", obj.id, user, {"name": obj.name})
    except Exception:
        pass
    return None


# Linking endpoints
class LinkRequest(BaseModel):
    item_id: int


class AssetLinkOut(BaseModel):
    id: int
    asset_id: int
    term_id: int


class ColumnLinkOut(BaseModel):
    id: int
    column_id: int
    term_id: int


@router.post("/{term_id}/assets", response_model=AssetLinkOut, status_code=status.HTTP_201_CREATED)
def link_asset(term_id: int, payload: LinkRequest, db: Session = Depends(get_session), user: User | None = Depends(require_writer)):
    link = AssetTermLink(asset_id=payload.item_id, term_id=term_id)
    db.add(link)
    db.commit()
    db.refresh(link)
    return AssetLinkOut(id=link.id, asset_id=link.asset_id, term_id=link.term_id)


@router.delete("/{term_id}/assets/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_asset(term_id: int, link_id: int, db: Session = Depends(get_session), user: User | None = Depends(require_writer)):
    link = db.query(AssetTermLink).filter(AssetTermLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Not found")
    from datetime import datetime
    link.deleted_at = datetime.utcnow()
    db.commit()
    return None


@router.get("/{term_id}/assets", response_model=List[AssetLinkOut])
def list_asset_links(term_id: int, db: Session = Depends(get_session)):
    rows = db.query(AssetTermLink).filter(AssetTermLink.term_id == term_id, AssetTermLink.deleted_at.is_(None)).all()
    return [AssetLinkOut(id=r.id, asset_id=r.asset_id, term_id=r.term_id) for r in rows]


@router.post("/{term_id}/columns", response_model=ColumnLinkOut, status_code=status.HTTP_201_CREATED)
def link_column(term_id: int, payload: LinkRequest, db: Session = Depends(get_session), user: User | None = Depends(require_writer)):
    link = ColumnTermLink(column_id=payload.item_id, term_id=term_id)
    db.add(link)
    db.commit()
    db.refresh(link)
    return ColumnLinkOut(id=link.id, column_id=link.column_id, term_id=link.term_id)


@router.delete("/{term_id}/columns/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_column(term_id: int, link_id: int, db: Session = Depends(get_session), user: User | None = Depends(require_writer)):
    link = db.query(ColumnTermLink).filter(ColumnTermLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Not found")
    from datetime import datetime
    link.deleted_at = datetime.utcnow()
    db.commit()
    return None


@router.get("/{term_id}/columns", response_model=List[ColumnLinkOut])
def list_column_links(term_id: int, db: Session = Depends(get_session)):
    rows = db.query(ColumnTermLink).filter(ColumnTermLink.term_id == term_id, ColumnTermLink.deleted_at.is_(None)).all()
    return [ColumnLinkOut(id=r.id, column_id=r.column_id, term_id=r.term_id) for r in rows]
