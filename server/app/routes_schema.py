"""Schema API: categories, criteria, places, settings — and the admin CRUD.

The browser reads `GET /api/schema` on load and builds its whole form and
scoring model from the response. Everything is scoped to the signed-in user, so
"admin" here means "admin of your own configuration", not a privileged role.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import require_user
from .db import get_session
from .models import Candidate, Category, Criterion, Place, Setting
from .seed import SETTINGS as DEFAULT_SETTINGS
from .seed import seed_user

router = APIRouter(prefix="/api", tags=["schema"])

KINDS = {"num", "yesno", "r3", "enum", "date", "datetime", "text", "textarea",
         "budget", "distance", "calc"}
IMPORTANCE = {"must", "important", "nice", "none"}
KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")
    return (s or "field")[:64]


# ----------------------------------------------------------------- payloads
class CategoryIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    key: str | None = None
    color: str = "#4d4d4d"
    sort: int | None = None
    archived: bool | None = None


class CriterionIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    key: str | None = None
    category_key: str | None = None
    kind: str = "yesno"
    importance: str = "important"
    weight_override: float | None = None
    hint: str | None = None
    options: list[dict] | None = None
    config: dict | None = None
    scored: bool = True
    photo_evidence: bool = False
    scrapable: bool = True
    sort: int | None = None
    archived: bool | None = None

    @field_validator("kind")
    @classmethod
    def _kind(cls, v):
        if v not in KINDS:
            raise ValueError(f"kind must be one of {sorted(KINDS)}")
        return v

    @field_validator("importance")
    @classmethod
    def _imp(cls, v):
        if v not in IMPORTANCE:
            raise ValueError(f"importance must be one of {sorted(IMPORTANCE)}")
        return v


class PlaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    key: str | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    weight: float = 2
    depart_hour: float | None = None
    modes: list[dict] = Field(default_factory=list)
    sort: int | None = None
    archived: bool | None = None


# ----------------------------------------------------------------- helpers
def cat_json(c: Category) -> dict:
    return {"id": c.id, "key": c.key, "title": c.title, "color": c.color,
            "sort": c.sort, "archived": c.archived}


def crit_json(c: Criterion, cat_key: str | None) -> dict:
    return {"id": c.id, "key": c.key, "label": c.label, "hint": c.hint,
            "kind": c.kind, "category_key": cat_key,
            "importance": c.importance,
            "weight_override": float(c.weight_override) if c.weight_override is not None else None,
            "weight": c.weight, "options": c.options, "config": c.config,
            "scored": c.scored, "photo_evidence": c.photo_evidence,
            "scrapable": c.scrapable, "sort": c.sort, "archived": c.archived,
            "builtin": c.builtin}


def place_json(p: Place) -> dict:
    return {"id": p.id, "key": p.key, "name": p.name, "address": p.address,
            "lat": p.lat, "lon": p.lon, "weight": float(p.weight),
            "departHour": float(p.depart_hour) if p.depart_hour is not None else None,
            "modes": p.modes, "sort": p.sort, "archived": p.archived}


async def load_schema(session: AsyncSession, uid: str) -> dict:
    cats = (await session.execute(
        select(Category).where(Category.uid == uid).order_by(Category.sort, Category.id)
    )).scalars().all()
    crits = (await session.execute(
        select(Criterion).where(Criterion.uid == uid).order_by(Criterion.sort, Criterion.id)
    )).scalars().all()
    places = (await session.execute(
        select(Place).where(Place.uid == uid).order_by(Place.sort, Place.id)
    )).scalars().all()
    rows = (await session.execute(
        select(Setting).where(Setting.uid == uid))).scalars().all()

    by_id = {c.id: c.key for c in cats}
    settings = dict(DEFAULT_SETTINGS)
    for r in rows:
        settings[r.key] = (r.value or {}).get("v")

    return {
        "categories": [cat_json(c) for c in cats],
        "criteria": [crit_json(c, by_id.get(c.category_id)) for c in crits],
        "places": [place_json(p) for p in places],
        "settings": settings,
    }


async def _cat_or_404(session, uid, cat_id) -> Category:
    c = await session.get(Category, cat_id)
    if not c or c.uid != uid:
        raise HTTPException(404, "no such category")
    return c


async def _crit_or_404(session, uid, crit_id) -> Criterion:
    c = await session.get(Criterion, crit_id)
    if not c or c.uid != uid:
        raise HTTPException(404, "no such criterion")
    return c


async def _unique_key(session, model, uid, wanted: str, exclude_id=None) -> str:
    base = _slug(wanted)
    key, n = base, 1
    while True:
        q = select(model.id).where(model.uid == uid, model.key == key)
        if exclude_id:
            q = q.where(model.id != exclude_id)
        if not (await session.execute(q)).first():
            return key
        n += 1
        key = f"{base}_{n}"[:64]


# ----------------------------------------------------------------- routes
@router.get("/schema")
async def get_schema(user=Depends(require_user), session: AsyncSession = Depends(get_session)):
    seeded = await seed_user(session, user["sub"], user.get("email"))
    await session.commit()
    data = await load_schema(session, user["sub"])
    data["seeded"] = seeded
    return data


@router.post("/admin/categories")
async def create_category(body: CategoryIn, user=Depends(require_user),
                          session: AsyncSession = Depends(get_session)):
    uid = user["sub"]
    key = await _unique_key(session, Category, uid, body.key or body.title)
    if body.sort is None:
        rows = (await session.execute(select(Category.sort).where(Category.uid == uid))).scalars().all()
        body.sort = (max(rows) + 1) if rows else 0
    c = Category(uid=uid, key=key, title=body.title, color=body.color, sort=body.sort)
    session.add(c)
    await session.commit()
    return cat_json(c)


@router.patch("/admin/categories/{cat_id}")
async def update_category(cat_id: int, body: CategoryIn, user=Depends(require_user),
                          session: AsyncSession = Depends(get_session)):
    c = await _cat_or_404(session, user["sub"], cat_id)
    c.title = body.title
    c.color = body.color
    if body.sort is not None:
        c.sort = body.sort
    if body.archived is not None:
        c.archived = body.archived
    await session.commit()
    return cat_json(c)


@router.delete("/admin/categories/{cat_id}")
async def delete_category(cat_id: int, user=Depends(require_user),
                          session: AsyncSession = Depends(get_session)):
    """Archives the category and everything under it. Recorded answers survive."""
    uid = user["sub"]
    c = await _cat_or_404(session, uid, cat_id)
    kids = (await session.execute(
        select(Criterion).where(Criterion.uid == uid, Criterion.category_id == c.id)
    )).scalars().all()
    for k in kids:
        k.archived = True
    c.archived = True
    await session.commit()
    return {"archived_category": c.key, "archived_criteria": [k.key for k in kids]}


@router.post("/admin/criteria")
async def create_criterion(body: CriterionIn, user=Depends(require_user),
                           session: AsyncSession = Depends(get_session)):
    uid = user["sub"]
    cat_id = None
    if body.category_key:
        row = (await session.execute(select(Category).where(
            Category.uid == uid, Category.key == body.category_key))).scalar_one_or_none()
        if not row:
            raise HTTPException(400, f"no category '{body.category_key}'")
        cat_id = row.id
    key = await _unique_key(session, Criterion, uid, body.key or body.label)
    if body.sort is None:
        rows = (await session.execute(select(Criterion.sort).where(Criterion.uid == uid))).scalars().all()
        body.sort = (max(rows) + 1) if rows else 0
    c = Criterion(uid=uid, category_id=cat_id, key=key, label=body.label,
                  kind=body.kind, importance=body.importance,
                  weight_override=body.weight_override, hint=body.hint,
                  options=body.options, config=body.config, scored=body.scored,
                  photo_evidence=body.photo_evidence, scrapable=body.scrapable,
                  sort=body.sort, builtin=False)
    session.add(c)
    await session.commit()
    return crit_json(c, body.category_key)


@router.patch("/admin/criteria/{crit_id}")
async def update_criterion(crit_id: int, body: CriterionIn, user=Depends(require_user),
                           session: AsyncSession = Depends(get_session)):
    uid = user["sub"]
    c = await _crit_or_404(session, uid, crit_id)
    if body.category_key is not None:
        row = (await session.execute(select(Category).where(
            Category.uid == uid, Category.key == body.category_key))).scalar_one_or_none()
        c.category_id = row.id if row else None
    # The key is what candidate answers are filed under; renaming it would
    # orphan every recorded value, so it is deliberately immutable.
    c.label = body.label
    c.kind = body.kind
    c.importance = body.importance
    c.weight_override = body.weight_override
    c.hint = body.hint
    c.options = body.options
    c.config = body.config
    c.scored = body.scored
    c.photo_evidence = body.photo_evidence
    c.scrapable = body.scrapable
    if body.sort is not None:
        c.sort = body.sort
    if body.archived is not None:
        c.archived = body.archived
    await session.commit()
    return crit_json(c, body.category_key)


@router.delete("/admin/criteria/{crit_id}")
async def delete_criterion(crit_id: int, hard: bool = False, user=Depends(require_user),
                           session: AsyncSession = Depends(get_session)):
    """Archive by default. Hard delete refuses on built-ins and still keeps the
    answers already recorded on candidates — those are data, not schema."""
    c = await _crit_or_404(session, user["sub"], crit_id)
    if hard and c.builtin:
        raise HTTPException(400, "built-in criteria can be archived but not deleted")
    if hard:
        await session.delete(c)
        await session.commit()
        return {"deleted": c.key}
    c.archived = True
    await session.commit()
    return {"archived": c.key}


@router.put("/admin/settings")
async def put_settings(body: dict, user=Depends(require_user),
                       session: AsyncSession = Depends(get_session)):
    uid = user["sub"]
    rows = {r.key: r for r in (await session.execute(
        select(Setting).where(Setting.uid == uid))).scalars().all()}
    for k, v in (body or {}).items():
        if k in rows:
            rows[k].value = {"v": v}
        else:
            session.add(Setting(uid=uid, key=k, value={"v": v}))
    await session.commit()
    return (await load_schema(session, uid))["settings"]


@router.post("/admin/places")
async def create_place(body: PlaceIn, user=Depends(require_user),
                       session: AsyncSession = Depends(get_session)):
    uid = user["sub"]
    key = await _unique_key(session, Place, uid, body.key or body.name)
    p = Place(uid=uid, key=key, name=body.name, address=body.address, lat=body.lat,
              lon=body.lon, weight=body.weight, depart_hour=body.depart_hour,
              modes=body.modes, sort=body.sort or 0)
    session.add(p)
    await session.commit()
    return place_json(p)


@router.patch("/admin/places/{place_id}")
async def update_place(place_id: int, body: PlaceIn, user=Depends(require_user),
                       session: AsyncSession = Depends(get_session)):
    p = await session.get(Place, place_id)
    if not p or p.uid != user["sub"]:
        raise HTTPException(404, "no such place")
    p.name, p.address, p.weight = body.name, body.address, body.weight
    p.lat, p.lon, p.depart_hour, p.modes = body.lat, body.lon, body.depart_hour, body.modes
    if body.sort is not None:
        p.sort = body.sort
    if body.archived is not None:
        p.archived = body.archived
    await session.commit()
    return place_json(p)


@router.delete("/admin/places/{place_id}")
async def delete_place(place_id: int, user=Depends(require_user),
                       session: AsyncSession = Depends(get_session)):
    p = await session.get(Place, place_id)
    if not p or p.uid != user["sub"]:
        raise HTTPException(404, "no such place")
    await session.delete(p)
    await session.commit()
    return {"deleted": p.key}


@router.get("/admin/usage/{crit_key}")
async def criterion_usage(crit_key: str, user=Depends(require_user),
                          session: AsyncSession = Depends(get_session)):
    """How many candidates have an answer for this criterion — shown before
    archiving so the consequences are visible rather than guessed at."""
    rows = (await session.execute(select(Candidate.answers).where(
        Candidate.uid == user["sub"]))).scalars().all()
    used = sum(1 for a in rows if (a or {}).get(crit_key) not in (None, ""))
    return {"key": crit_key, "candidates_with_value": used, "candidates_total": len(rows)}
