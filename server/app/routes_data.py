"""Candidate CRUD.

Conflict handling keeps the shape the browser already had: each candidate
carries a client timestamp, and a write only lands if it is at least as new as
what is stored. Two devices editing different flats never collide; two devices
editing the same flat resolve last-write-wins, and the loser is told so rather
than silently overwritten.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import require_user
from .db import get_session
from .models import Candidate

router = APIRouter(prefix="/api", tags=["candidates"])


class CandidateIn(BaseModel):
    ext_id: str = Field(min_length=1, max_length=64)
    address: str | None = None
    link: str | None = None
    notes: str | None = None
    lat: float | None = None
    lon: float | None = None
    photos: list[str] = Field(default_factory=list)
    answers: dict = Field(default_factory=dict)
    travel: dict = Field(default_factory=dict)
    scrape: dict | None = None
    status_override: str | None = None
    archived: bool = False
    client_updated_at: int = 0


def cand_json(c: Candidate) -> dict:
    return {"id": c.id, "ext_id": c.ext_id, "address": c.address, "link": c.link,
            "notes": c.notes, "lat": c.lat, "lon": c.lon, "photos": c.photos,
            "answers": c.answers, "travel": c.travel, "scrape": c.scrape,
            "status_override": c.status_override, "archived": c.archived,
            "client_updated_at": c.client_updated_at,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None}


@router.get("/candidates")
async def list_candidates(include_archived: bool = False, user=Depends(require_user),
                          session: AsyncSession = Depends(get_session)):
    q = select(Candidate).where(Candidate.uid == user["sub"])
    if not include_archived:
        q = q.where(Candidate.archived.is_(False))
    rows = (await session.execute(q.order_by(Candidate.id.desc()))).scalars().all()
    return {"candidates": [cand_json(c) for c in rows], "server_time": int(time.time() * 1000)}


@router.put("/candidates/{ext_id}")
async def upsert_candidate(ext_id: str, body: CandidateIn, user=Depends(require_user),
                           session: AsyncSession = Depends(get_session)):
    uid = user["sub"]
    row = (await session.execute(select(Candidate).where(
        Candidate.uid == uid, Candidate.ext_id == ext_id))).scalar_one_or_none()

    if row is None:
        row = Candidate(uid=uid, ext_id=ext_id)
        session.add(row)
    elif body.client_updated_at < row.client_updated_at:
        # Somebody else's newer edit is already stored. Hand it back rather than
        # clobbering it; the caller merges and retries.
        raise HTTPException(status_code=409, detail={
            "reason": "stale write", "current": cand_json(row)})

    for f in ("address", "link", "notes", "lat", "lon", "photos", "answers",
              "travel", "scrape", "status_override", "archived"):
        setattr(row, f, getattr(body, f))
    row.client_updated_at = body.client_updated_at or int(time.time() * 1000)
    await session.commit()
    return cand_json(row)


@router.post("/candidates/bulk")
async def bulk_upsert(body: list[CandidateIn], user=Depends(require_user),
                      session: AsyncSession = Depends(get_session)):
    """One-shot import — used when moving existing browser data to the server."""
    uid = user["sub"]
    existing = {c.ext_id: c for c in (await session.execute(
        select(Candidate).where(Candidate.uid == uid))).scalars().all()}
    written, skipped = [], []
    for item in body:
        row = existing.get(item.ext_id)
        if row is None:
            row = Candidate(uid=uid, ext_id=item.ext_id)
            session.add(row)
        elif item.client_updated_at < row.client_updated_at:
            skipped.append(item.ext_id)
            continue
        for f in ("address", "link", "notes", "lat", "lon", "photos", "answers",
                  "travel", "scrape", "status_override", "archived"):
            setattr(row, f, getattr(item, f))
        row.client_updated_at = item.client_updated_at or int(time.time() * 1000)
        written.append(item.ext_id)
    await session.commit()
    return {"written": written, "skipped_older": skipped}


@router.delete("/candidates/{ext_id}")
async def delete_candidate(ext_id: str, hard: bool = False, user=Depends(require_user),
                           session: AsyncSession = Depends(get_session)):
    uid = user["sub"]
    row = (await session.execute(select(Candidate).where(
        Candidate.uid == uid, Candidate.ext_id == ext_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "no such candidate")
    if hard:
        await session.delete(row)
    else:
        row.archived = True
        row.client_updated_at = int(time.time() * 1000)
    await session.commit()
    return {"deleted" if hard else "archived": ext_id}
