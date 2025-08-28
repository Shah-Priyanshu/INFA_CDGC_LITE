from __future__ import annotations

import re
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import ColumnModel, ColumnClassification
from ..security import require_writer, User, get_current_user
from ..audit import audit_log

router = APIRouter(prefix="/classification", tags=["classification"])


# Rule-based detectors per plan (no mocks)
# Very conservative regexes to minimize false positives
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+\d{1,3}[\s-]?)?(?:\(\d{2,3}\)[\s-]?|\d{2,4}[\s-])?\d{3}[\s-]?\d{4}\b")
DOB_RE = re.compile(r"\b(?:19|20)\d{2}[-/](?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12]\d|3[01])\b")
# Basic Luhn check for credit cards, masked example capture
CC_LUHN_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


class ClassificationRequest(BaseModel):
    column_id: int
    detectors: List[str] | None = None  # default to all


class ClassificationOut(BaseModel):
    id: int
    column_id: int
    detector: str
    score: int
    matched_example: str | None


@router.post("/run", response_model=List[ClassificationOut])
def run_classification(
    payload: ClassificationRequest,
    db: Session = Depends(get_session),
    user: User | None = Depends(require_writer),
):
    col = db.query(ColumnModel).filter(ColumnModel.id == payload.column_id, ColumnModel.deleted_at.is_(None)).first()
    if not col:
        raise HTTPException(status_code=404, detail="Column not found")

    # Load a small sample from scan artifacts or column description/name as a heuristic
    # For now, we classify using column name/description as the input text per MVP
    text = f"{col.name} {col.description or ''}"

    detectors = payload.detectors or ["email", "phone", "dob", "cc"]
    results: list[ColumnClassification] = []

    def add_result(det: str, matched: str | None, score: int):
        rec = ColumnClassification(column_id=col.id, detector=det, matched_example=matched, score=score)
        db.add(rec)
        results.append(rec)

    if "email" in detectors and EMAIL_RE.search(text):
        add_result("email", EMAIL_RE.search(text).group(0), 90)
    if "phone" in detectors and PHONE_RE.search(text):
        add_result("phone", PHONE_RE.search(text).group(0), 70)
    if "dob" in detectors and DOB_RE.search(text):
        add_result("dob", DOB_RE.search(text).group(0), 80)
    if "cc" in detectors:
        m = CC_LUHN_RE.search(text)
        if m:
            # Luhn validate digits
            digits = [int(d) for d in re.sub(r"\D", "", m.group(0))]
            def luhn_ok(ds: list[int]) -> bool:
                s = 0
                alt = False
                for d in reversed(ds):
                    d2 = d * 2 if alt else d
                    if d2 > 9:
                        d2 -= 9
                    s += d2
                    alt = not alt
                return s % 10 == 0
            if 13 <= len(digits) <= 19 and luhn_ok(digits):
                add_result("cc", m.group(0), 95)

    if results:
        db.commit()
    return [ClassificationOut(id=r.id, column_id=r.column_id, detector=r.detector, score=r.score, matched_example=r.matched_example) for r in results]
