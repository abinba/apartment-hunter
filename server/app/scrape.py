"""Fetch a listing through ScrapingBee and pull out text plus photo URLs."""
from __future__ import annotations

import asyncio
import io
import logging
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from PIL import Image

log = logging.getLogger("scrape")

SB_ENDPOINT = "https://app.scrapingbee.com/api/v1/"

# Junk that appears in every gallery and tells the model nothing.
_SKIP_IMG = re.compile(
    r"(logo|icon|sprite|avatar|placeholder|favicon|badge|banner|pixel|blank|"
    r"static/|/assets/|\.svg($|\?))", re.I)


async def fetch_html(url: str, api_key: str) -> str:
    params = {
        "api_key": api_key,
        "url": url,
        "render_js": "true",
        "wait": "3000",
        "country_code": "pl",
        "block_resources": "false",   # gallery images are often lazy-loaded
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.get(SB_ENDPOINT, params=params)
    if r.status_code == 401:
        raise RuntimeError("ScrapingBee rejected the API key")
    if r.status_code == 402:
        raise RuntimeError("ScrapingBee credits exhausted")
    if r.status_code >= 400:
        raise RuntimeError(f"ScrapingBee returned {r.status_code}: {r.text[:200]}")
    return r.text


def _clean_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def parse_listing(html: str, url: str) -> dict:
    """Return {title, text, images[], meta{}} for any listing page.

    Otodom embeds a __NEXT_DATA__ blob with clean structured fields; OLX has a
    parameters block. Everything else falls back to visible text, which the
    model copes with well enough.
    """
    soup = BeautifulSoup(html, "lxml")
    out = {"title": "", "text": "", "images": [], "meta": {}, "source": "generic"}

    title_el = soup.find("h1") or soup.find("title")
    out["title"] = title_el.get_text(strip=True) if title_el else ""

    # --- Otodom ------------------------------------------------------------
    nxt = soup.find("script", id="__NEXT_DATA__")
    if nxt and nxt.string:
        try:
            import json
            ad = json.loads(nxt.string)["props"]["pageProps"]["ad"]
            t = ad.get("target") or {}
            out["source"] = "otodom"
            out["title"] = ad.get("title") or out["title"]
            desc = BeautifulSoup(ad.get("description") or "", "lxml").get_text("\n", strip=True)
            out["text"] = desc
            out["meta"] = {k: v for k, v in {
                "price": t.get("Price"), "czynsz": t.get("Rent"), "kaucja": t.get("Deposit"),
                "area": t.get("Area"), "rooms": t.get("Rooms_num"), "floor": t.get("Floor_no"),
                "heating": t.get("Heating"), "build_year": t.get("Build_year"),
                "extras": t.get("Extras_types"), "equipment": t.get("Equipment_types"),
                "media": t.get("Media_types"),
            }.items() if v not in (None, [], "")}
            loc = (ad.get("location") or {}).get("coordinates") or {}
            if loc.get("latitude"):
                out["meta"]["lat"] = loc["latitude"]
                out["meta"]["lon"] = loc["longitude"]
            for im in (ad.get("images") or []):
                u = im.get("large") or im.get("medium") or im.get("small")
                if u:
                    out["images"].append(u.split("?")[0])
        except Exception as e:  # noqa: BLE001 — fall through to generic parsing
            log.info("otodom parse failed, falling back: %s", e)

    # --- OLX ---------------------------------------------------------------
    if not out["text"]:
        params_box = soup.select("[data-testid='ad-parameters-container'] p")
        if params_box:
            out["source"] = "olx"
            out["meta"]["parameters"] = [p.get_text(" ", strip=True) for p in params_box]
        desc = soup.select_one("[data-cy='ad_description']")
        price = soup.select_one("[data-testid='ad-price-container']")
        if price:
            out["meta"]["price_text"] = price.get_text(" ", strip=True)
        crumbs = [li.get_text(strip=True) for li in soup.select("nav li")]
        if crumbs:
            out["meta"]["breadcrumb"] = crumbs[-3:]
        out["text"] = desc.get_text("\n", strip=True) if desc else _clean_text(soup)

    # --- images ------------------------------------------------------------
    if not out["images"]:
        seen = set()
        for img in soup.find_all("img"):
            src = (img.get("src") or img.get("data-src") or "").strip()
            if not src or _SKIP_IMG.search(src):
                continue
            src = urljoin(url, src).split(";s=")[0]
            if src not in seen:
                seen.add(src)
                out["images"].append(src)

    out["text"] = (out["text"] or "")[:24000]
    return out


async def download_photos(urls: list[str], limit: int, max_px: int) -> list[dict]:
    """Download, downscale and JPEG-encode. Returns [{media_type, data}]."""
    async def one(client: httpx.AsyncClient, u: str):
        try:
            r = await client.get(u, timeout=30, follow_redirects=True)
            if r.status_code >= 400 or len(r.content) < 4000:
                return None                      # tiny files are icons, not rooms
            im = Image.open(io.BytesIO(r.content))
            im = im.convert("RGB")
            im.thumbnail((max_px, max_px), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=80, optimize=True)
            return {"media_type": "image/jpeg", "data": buf.getvalue()}
        except Exception as e:  # noqa: BLE001
            log.info("photo skipped %s: %s", u[:80], e)
            return None

    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
        got = await asyncio.gather(*[one(client, u) for u in urls[: limit * 2]])
    return [g for g in got if g][:limit]
