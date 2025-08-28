from __future__ import annotations

from typing import List, Deque, Literal, Dict, Any
from collections import deque
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import LineageEdge, Asset
from ..security import require_writer, User, get_current_user
from ..audit import audit_log

try:
    import sqlglot
except Exception:  # pragma: no cover
    sqlglot = None


router = APIRouter(prefix="/lineage", tags=["lineage"])


class LineageGraph(BaseModel):
    nodes: List[int] = []
    edges: List[tuple[int, int]] = []


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


@router.get("/graph")
def lineage_graph(
    asset_id: int | None = None,
    depth: int = 1,
    format: Literal["ids", "ui"] = "ids",
    db: Session = Depends(get_session),
    user: User | None = Depends(get_current_user),
):
    # If no asset_id is provided, return the entire edge list
    if asset_id is None:
        # Build aliases for visibility filtering on both endpoints
        from sqlalchemy.orm import aliased
        A = aliased(Asset)
        B = aliased(Asset)
        edges = (
            db.query(LineageEdge, A, B)
            .join(A, A.id == LineageEdge.src_asset_id)
            .join(B, B.id == LineageEdge.dst_asset_id)
            .filter(LineageEdge.deleted_at.is_(None), A.deleted_at.is_(None), B.deleted_at.is_(None))
            .filter(_visibility_clause(A, user))
            .filter(_visibility_clause(B, user))
        ).all()
        nodes = set()
        pairs: list[tuple[int, int]] = []
        for e, a_src, a_dst in edges:
            nodes.add(e.src_asset_id)
            nodes.add(e.dst_asset_id)
            pairs.append((e.src_asset_id, e.dst_asset_id))
        if format == "ui":
            # Build node metadata
            assets = {
                a.id: a
                for a in db.query(Asset)
                .filter(Asset.id.in_(nodes), Asset.deleted_at.is_(None))
                .filter(_visibility_clause(Asset, user))
                .all()
            }
            return {
                "nodes": [
                    {"id": i, "name": assets.get(i).name if assets.get(i) else str(i), "system_id": assets.get(i).system_id if assets.get(i) else None}
                    for i in sorted(nodes)
                ],
                "edges": [{"source": s, "target": t} for (s, t) in pairs],
            }
        return LineageGraph(nodes=sorted(nodes), edges=pairs)

    # Constrained traversal: BFS up to `depth` in both directions from the starting asset
    # Check start asset visibility
    visible_start = (
        db.query(Asset.id)
        .filter(Asset.id == asset_id, Asset.deleted_at.is_(None))
        .filter(_visibility_clause(Asset, user))
        .first()
        is not None
    )
    if not visible_start:
        return LineageGraph(nodes=[], edges=[])
    # Load only edges whose src and dst are both visible
    from sqlalchemy.orm import aliased
    A = aliased(Asset)
    B = aliased(Asset)
    rows = (
        db.query(LineageEdge, A.id, B.id)
        .join(A, A.id == LineageEdge.src_asset_id)
        .join(B, B.id == LineageEdge.dst_asset_id)
        .filter(LineageEdge.deleted_at.is_(None), A.deleted_at.is_(None), B.deleted_at.is_(None))
        .filter(_visibility_clause(A, user))
        .filter(_visibility_clause(B, user))
        .all()
    )
    edges = []
    for e, _sid, _did in rows:
        edges.append(e)
    out_adj: dict[int, list[int]] = {}
    in_adj: dict[int, list[int]] = {}
    for e in edges:
        out_adj.setdefault(e.src_asset_id, []).append(e.dst_asset_id)
        in_adj.setdefault(e.dst_asset_id, []).append(e.src_asset_id)

    visited: dict[int, int] = {asset_id: 0}
    q: Deque[int] = deque([asset_id])
    pairs: set[tuple[int, int]] = set()
    while q:
        node = q.popleft()
        dist = visited[node]
        if dist >= depth:
            continue
        # explore outgoing
        for nbr in out_adj.get(node, []):
            pairs.add((node, nbr))
            if nbr not in visited or visited[nbr] > dist + 1:
                visited[nbr] = dist + 1
                q.append(nbr)
        # explore incoming
        for nbr in in_adj.get(node, []):
            pairs.add((nbr, node))
            if nbr not in visited or visited[nbr] > dist + 1:
                visited[nbr] = dist + 1
                q.append(nbr)

    if format == "ui":
        node_ids = sorted(visited.keys())
        assets = {
            a.id: a
            for a in db.query(Asset)
            .filter(Asset.id.in_(node_ids), Asset.deleted_at.is_(None))
            .filter(_visibility_clause(Asset, user))
            .all()
        }
        return {
            "nodes": [
                {"id": i, "name": assets.get(i).name if assets.get(i) else str(i), "system_id": assets.get(i).system_id if assets.get(i) else None}
                for i in node_ids
            ],
            "edges": [{"source": s, "target": t} for (s, t) in sorted(pairs)],
        }
    return LineageGraph(nodes=sorted(visited.keys()), edges=sorted(pairs))


class SQLLineageRequest(BaseModel):
    sql: str


class SQLLineageResponse(BaseModel):
    sources: list[str]
    targets: list[str]


@router.post("/sql", response_model=SQLLineageResponse)
def lineage_from_sql(
    payload: SQLLineageRequest,
    persist: int = Query(0, ge=0, le=1),
    db: Session = Depends(get_session),
    user: User | None = Depends(require_writer),
):
    # Parse sources and targets via sqlglot where possible
    sources: list[str] = []
    targets: list[str] = []
    if not sqlglot:
        return SQLLineageResponse(sources=sources, targets=targets)

    try:
        parsed = sqlglot.parse_one(payload.sql)
        # Collect all referenced tables as potential sources
        for t in parsed.find_all(sqlglot.exp.Table):
            fq = ".".join([p for p in [t.catalog, t.db, t.name] if p])
            if fq and fq not in sources:
                sources.append(fq)

        # Determine common targets (INSERT INTO, CREATE TABLE, CTAS)
        for node in parsed.find_all((sqlglot.exp.Insert, sqlglot.exp.Create)):
            # INSERT INTO target
            if isinstance(node, sqlglot.exp.Insert):
                tgt = node.this
                if isinstance(tgt, sqlglot.exp.Table):
                    fq = ".".join([p for p in [tgt.catalog, tgt.db, tgt.name] if p])
                    if fq and fq not in targets:
                        targets.append(fq)
            # CREATE TABLE target
            if isinstance(node, sqlglot.exp.Create):
                tgt = node.this
                if isinstance(tgt, sqlglot.exp.Table):
                    fq = ".".join([p for p in [tgt.catalog, tgt.db, tgt.name] if p])
                    if fq and fq not in targets:
                        targets.append(fq)
    except Exception:
        # Best-effort; return what we have
        pass

    # If persisting, create LineageEdge records for all source->target combinations
    if persist:
        # Map asset names to IDs when possible
        # Strategy: try exact match first; if not found, fall back to last identifier segment
        # Prefer the most recently created assets to avoid picking stale fixtures from other tests/systems
        assets = (
            db.query(Asset)
            .filter(Asset.deleted_at.is_(None))
            .order_by(Asset.id.desc())
            .all()
        )
        assets_by_name: dict[str, list[Asset]] = {}
        assets_by_tail: dict[str, list[Asset]] = {}
        for a in assets:
            assets_by_name.setdefault(a.name, []).append(a)
            tail = a.name.split(".")[-1]
            assets_by_tail.setdefault(tail, []).append(a)

        def resolve_asset_id(name: str) -> int | None:
            # Newest exact match globally (lists are pre-sorted by id desc)
            if assets_by_name.get(name):
                return assets_by_name[name][0].id
            # Fallback to newest by tail globally
            tail = name.split(".")[-1]
            if assets_by_tail.get(tail):
                return assets_by_tail[tail][0].id
            return None

        created = 0
        for t in targets:
            # Build candidate target assets (exact and by tail)
            t_tail = t.split(".")[-1]
            t_cands: list[tuple[int, int, bool]] = []  # (asset_id, system_id, is_exact)
            for a in assets_by_name.get(t, []):
                t_cands.append((a.id, a.system_id, True))
            for a in assets_by_tail.get(t_tail, []):
                if (a.id, a.system_id, True) not in t_cands:
                    t_cands.append((a.id, a.system_id, False))
            if not t_cands:
                continue

            for s in sources:
                s_tail = s.split(".")[-1]
                s_cands: list[tuple[int, int, bool]] = []  # (asset_id, system_id, is_exact)
                for a in assets_by_name.get(s, []):
                    s_cands.append((a.id, a.system_id, True))
                for a in assets_by_tail.get(s_tail, []):
                    if (a.id, a.system_id, True) not in s_cands:
                        s_cands.append((a.id, a.system_id, False))
                if not s_cands:
                    continue

                # Prefer same-system pairs; score by exactness then by recency of the pair
                best_pair: tuple[int, int] | None = None
                best_score: tuple[int, int] = (-1, -1)  # (exact_score, min_pair_id)
                for (tid, tsys, t_exact) in t_cands:
                    for (sid, ssys, s_exact) in s_cands:
                        if tsys != ssys:
                            continue
                        if sid == tid:
                            continue
                        exact_score = (1 if t_exact else 0) + (1 if s_exact else 0)
                        min_pair_id = min(sid, tid)
                        score = (exact_score, min_pair_id)
                        if score > best_score:
                            best_score = score
                            best_pair = (sid, tid)

                # If no same-system pair found, fall back to globally best by exactness/recency
                if best_pair is None:
                    for (tid, _tsys, t_exact) in t_cands:
                        for (sid, _ssys, s_exact) in s_cands:
                            if sid == tid:
                                continue
                            exact_score = (1 if t_exact else 0) + (1 if s_exact else 0)
                            min_pair_id = min(sid, tid)
                            score = (exact_score, min_pair_id)
                            if score > best_score:
                                best_score = score
                                best_pair = (sid, tid)

                if best_pair is None:
                    continue

                src_id, dst_id = best_pair
                exists = (
                    db.query(LineageEdge)
                    .filter(
                        LineageEdge.src_asset_id == src_id,
                        LineageEdge.dst_asset_id == dst_id,
                        LineageEdge.deleted_at.is_(None),
                    )
                    .first()
                )
                if exists:
                    continue
                edge = LineageEdge(
                    src_asset_id=src_id,
                    dst_asset_id=dst_id,
                    confidence=50,
                    predicate="sqlglot",
                )
                db.add(edge)
                created += 1
        if created:
            db.commit()
        try:
            audit_log("persist_lineage_sql", "lineage_edge", None, user, {"created": created})
        except Exception:
            pass

    return SQLLineageResponse(sources=sources, targets=targets)
