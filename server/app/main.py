"""Apartment Hunter scraping API.

POST /api/scrape       -> {job_id}      (starts work, returns immediately)
GET  /api/scrape/{id}  -> job state     (poll for progress; browse meanwhile)
GET  /api/health       -> config sanity

Sign-in is required: the caller sends a Firebase ID token, which is verified
against Google's public certificates and checked against ALLOWED_EMAILS.
Without that, anyone who found the URL could spend your ScrapingBee credits
and Anthropic tokens.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, HttpUrl

from .analyze import client_for, pass_photos, pass_reconcile, pass_text, tidy, usage_sum
from .auth import require_user
from .config import Config
from .db import SessionLocal, engine
from .models import Criterion
from .schema import LiveSchema, fields_from_db
from .routes_data import router as data_router
from .routes_schema import router as schema_router
from .scrape import download_photos, fetch_html, parse_listing

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("main")

app = FastAPI(title="Apartment Hunter scraper", docs_url=None, redoc_url=None)
app.state.cfg = Config()

app.include_router(schema_router)
app.include_router(data_router)


# Registered before CORSMiddleware so it sits *inside* it. Starlette's own
# ServerErrorMiddleware is outermost, so an unhandled exception returns a bare
# 500 with no Access-Control-Allow-Origin — the browser then hides the real
# error behind a misleading CORS message. Catching here keeps the response
# inside the CORS layer, so the actual reason reaches the console.
@app.middleware("http")
async def surface_errors(request, call_next):
    try:
        return await call_next(request)
    except Exception as e:  # noqa: BLE001
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500,
                            content={"detail": f"{type(e).__name__}: {str(e)[:300]}"})


app.add_middleware(
    CORSMiddleware,
    allow_origins=app.state.cfg.cors_origins or ["http://localhost:8000"],
    allow_credentials=False,
    # PATCH/PUT/DELETE are needed by the admin panel; without them the
    # browser blocks every edit at the preflight.
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

JOBS: dict[str, dict] = {}
DAILY: dict[str, list[float]] = defaultdict(list)

# Weighted so the bar moves at a believable pace: the photo pass is the slow one.
STAGES = [
    ("queued",     "Queued",                         0),
    ("fetching",   "Fetching the listing",           8),
    ("parsing",    "Reading the page",              20),
    ("photos",     "Downloading photographs",       30),
    ("text_pass",  "Analysing the description",     45),
    ("photo_pass", "Analysing the photographs",     65),
    ("reconcile",  "Reconciling text against photos", 88),
    ("done",       "Done",                         100),
]
STAGE_PCT = {k: p for k, _, p in STAGES}
STAGE_LABEL = {k: l for k, l, _ in STAGES}


class ScrapeIn(BaseModel):
    url: HttpUrl
    candidate_id: str | None = Field(default=None, max_length=64)


def _set(job_id: str, stage: str, **extra):
    j = JOBS.get(job_id)
    if not j:
        return
    j.update(stage=stage, stage_label=STAGE_LABEL.get(stage, stage),
             progress=STAGE_PCT.get(stage, j.get("progress", 0)),
             updated=time.time(), **extra)


def _sweep():
    ttl = app.state.cfg.job_ttl_s
    now = time.time()
    for k in [k for k, v in JOBS.items() if now - v.get("updated", now) > ttl]:
        JOBS.pop(k, None)


async def run_job(job_id: str, url: str, cfg: Config, uid: str):
    try:
        # The field list comes from this user's criteria, so anything added in
        # the admin panel is extracted from the very next listing — no deploy,
        # no code change. Falls back to the built-in list if the DB is empty.
        async with SessionLocal() as s:
            crits = (await s.execute(
                select(Criterion).where(Criterion.uid == uid))).scalars().all()
        ls = LiveSchema(fields_from_db(crits) or None)
        log.info("job %s scraping %d fields (%d photo-capable)",
                 job_id, len(ls.all_keys), len(ls.photo_keys))

        _set(job_id, "fetching")
        html = await fetch_html(url, cfg.scrapingbee_key)

        _set(job_id, "parsing")
        listing = parse_listing(html, url)
        _set(job_id, "photos", found_photos=len(listing["images"]))

        photos = await download_photos(listing["images"], cfg.max_photos, cfg.photo_max_px)
        _set(job_id, "text_pass", used_photos=len(photos))

        client = client_for(cfg.anthropic_key)

        text_raw, u1 = await pass_text(client, cfg.model, listing, ls)
        _set(job_id, "photo_pass", text_result=tidy(text_raw, ls))

        if photos:
            photo_raw, u2 = await pass_photos(client, cfg.model, photos, listing, ls)
        else:
            photo_raw, u2 = {}, None
        _set(job_id, "reconcile", photo_result=tidy(photo_raw, ls))

        final_raw, u3 = await pass_reconcile(client, cfg.model, text_raw, photo_raw,
                                            listing, ls)
        final = tidy(final_raw, ls)

        missing = sorted(k for k, v in final.items() if v.get("value") is None)
        low = sorted(k for k, v in final.items()
                     if v.get("value") is not None and (v.get("confidence") or 0) < 0.45)

        _set(job_id, "done",
             result=final,
             text_result=tidy(text_raw, ls),
             photo_result=tidy(photo_raw, ls),
             missing=missing,
             low_confidence=low,
             listing={"title": listing.get("title"), "source": listing.get("source"),
                      "images": listing["images"][:cfg.max_photos],
                      "lat": (listing.get("meta") or {}).get("lat"),
                      "lon": (listing.get("meta") or {}).get("lon")},
             usage=usage_sum(u1, u2, u3))
    except Exception as e:  # noqa: BLE001 — surfaced to the browser as job.error
        log.exception("job %s failed", job_id)
        _set(job_id, "error", error=str(e)[:400], progress=100)


@app.get("/api/health")
async def health():
    cfg = app.state.cfg
    problems = cfg.problems()
    db_ok, db_err = True, None
    try:
        async with SessionLocal() as s:
            await s.execute(text("select 1"))
    except Exception as e:  # noqa: BLE001
        db_ok, db_err = False, str(e)[:200]
        problems = problems + [f"database unreachable: {db_err}"]
    return {"ok": not problems, "problems": problems, "database": db_ok,
            "model": cfg.model, "max_photos": cfg.max_photos, "jobs": len(JOBS)}


@app.post("/api/scrape")
async def scrape(body: ScrapeIn, user: dict = Depends(require_user)):
    cfg = app.state.cfg
    if cfg.problems():
        raise HTTPException(status_code=503, detail="; ".join(cfg.problems()))
    _sweep()

    uid = user["sub"]
    now = time.time()
    DAILY[uid] = [t for t in DAILY[uid] if now - t < 86400]
    if len(DAILY[uid]) >= cfg.daily_job_cap:
        raise HTTPException(status_code=429,
                            detail=f"daily cap of {cfg.daily_job_cap} listings reached")
    running = sum(1 for j in JOBS.values()
                  if j["uid"] == uid and j["stage"] not in ("done", "error"))
    if running >= cfg.max_jobs_per_user:
        raise HTTPException(status_code=429, detail="too many scrapes running at once")
    DAILY[uid].append(now)

    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = dict(id=job_id, uid=uid, url=str(body.url),
                        candidate_id=body.candidate_id, stage="queued",
                        stage_label=STAGE_LABEL["queued"], progress=0,
                        created=now, updated=now)
    asyncio.create_task(run_job(job_id, str(body.url), cfg, uid))
    return {"job_id": job_id, "stages": [{"key": k, "label": l, "at": p} for k, l, p in STAGES]}


@app.get("/api/scrape/{job_id}")
async def job_state(job_id: str, user: dict = Depends(require_user)):
    j = JOBS.get(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="unknown or expired job")
    if j["uid"] != user["sub"]:
        raise HTTPException(status_code=403, detail="not your job")
    return {k: v for k, v in j.items() if k != "uid"}
