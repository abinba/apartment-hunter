"""Default categories, criteria, places and settings for a new user.

This is the hardcoded schema the browser used to carry, moved server-side
verbatim so nobody's existing data changes meaning. Weights match what was in
index.html: budget 8, the musts at 5, sunlight and mould at 4, important at 3
or 2, nice-to-haves at 1.

Seeding happens once per user, on first sign-in. After that the database is
authoritative and this file is never consulted again — editing it will not
retro-fit changes onto anyone who has already signed in.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Category, Criterion, Place, Setting, User

CATEGORIES = [
    ("track",    "Tracking & status",      "#25406e", 0),
    ("cost",     "Costs & size",           "#3d6b3a", 1),
    ("loc",      "Neighbourhood",          "#8a6d13", 2),
    ("apt",      "Building & apartment",   "#96521f", 3),
    ("contract", "Contract & admin",       "#4a3f78", 4),
    ("nice",     "Nice to have",           "#4d4d4d", 5),
]

# key, category, label, kind, importance, weight_override, hint,
# options, config, scored, photo_evidence
CRITERIA = [
    # --- tracking: recorded, never scored -----------------------------------
    ("address",   "track", "Address / district", "text", "none", None, None, None, None, False, False),
    ("link",      "track", "Listing link", "text", "none", None, None, None, None, False, False),
    ("availfrom", "track", "Available from", "date", "none", None,
     "Hard requirement — later than the cut-off rejects the flat.", None, None, False, False),
    ("messaged",  "track", "Messaged them?", "yesno", "none", None, None, None, None, False, False),
    ("msgdate",   "track", "Date messaged", "date", "none", None, None, None, None, False, False),
    ("presched",  "track", "Presentation scheduled?", "yesno", "none", None, None, None, None, False, False),
    ("presdate",  "track", "Presentation date", "datetime", "none", None, None, None, None, False, False),
    ("notes",     "track", "Notes & red flags", "textarea", "none", None, None, None, None, False, False),

    # --- costs ---------------------------------------------------------------
    ("rent",      "cost", "Rent (najem) zł/mo", "num", "none", None, None, None, None, False, False),
    ("admin",     "cost", "Czynsz administracyjny zł/mo", "num", "none", None, None, None, None, False, False),
    ("util",      "cost", "Media est. zł/mo", "num", "none", None, None, None, None, False, False),
    ("provision", "cost", "Provision fee zł (one-off)", "num", "none", None, None, None, None, False, False),
    ("kaucja",    "cost", "Kaucja zł (refundable)", "num", "none", None,
     "Not counted — you get it back.", None, None, False, False),
    ("area",      "cost", "Area m²", "num", "none", None,
     "Not scored — used for zł/m² only.", None, None, False, True),
    ("yearly",    "cost", "Yearly cost within budget", "budget", "must", 8.0,
     "12 × total monthly + provision. Full points to the budget, zero by 5% over.",
     None, None, True, False),

    # --- neighbourhood -------------------------------------------------------
    ("chain",     "loc", "Nearest grocery chain", "enum", "important", 3.0, None,
     [{"value": "Lidl", "points": 5}, {"value": "Auchan", "points": 4},
      {"value": "Netto", "points": 3}, {"value": "Biedronka", "points": 2},
      {"value": "Lewiatan", "points": 1}, {"value": "Other", "points": 0.5},
      {"value": "None nearby", "points": 0}], None, True, False),
    ("grocmin",   "loc", "Walk to grocery (min)", "distance", "important", 2.0, None,
     None, {"full": 5, "zero": 15}, True, False),
    ("transmin",  "loc", "Walk to transit (min)", "distance", "important", 2.0, None,
     None, {"full": 5, "zero": 12}, True, False),
    ("parkmin",   "loc", "Walk to park (min)", "distance", "nice", 1.0, None,
     None, {"full": 10, "zero": 25}, True, False),
    ("windows",   "loc", "Windows facing", "enum", "important", 2.0, None,
     [{"value": "East", "points": 1}, {"value": "East–North", "points": 1},
      {"value": "North", "points": 0.8}, {"value": "North–West", "points": 0.6},
      {"value": "South–East", "points": 0.8}, {"value": "South", "points": 0.55},
      {"value": "West", "points": 0.4}, {"value": "Other / unknown", "points": 0.3}],
     None, True, False),
    ("quiet",     "loc", "Quiet area", "r3", "important", 3.0,
     "0 busy road or nightlife, 3 clearly quiet residential.", None, None, True, False),
    ("neighbors", "loc", "Neighbours calm", "r3", "nice", 1.0, None, None, None, True, False),

    # --- the flat ------------------------------------------------------------
    ("bedroom",   "apt", "Separate bedroom", "yesno", "must", 5.0,
     "A studio or kawalerka is No.", None, None, True, True),
    ("heating",   "apt", "Central heating (miejskie)", "yesno", "must", 5.0, None, None, None, True, False),
    ("desk",      "apt", "Desk 140×90 fits", "yesno", "must", 5.0, None, None, None, True, True),
    ("piano",     "apt", "Piano 120×50 fits", "yesno", "must", 5.0, None, None, None, True, True),
    ("sun",       "apt", "Sunlight", "r3", "must", 4.0, None, None, None, True, True),
    ("nomold",    "apt", "No damp / mould", "yesno", "must", 4.0,
     "Only answer No on visible evidence. Absence of evidence is blank, not No.",
     None, None, True, True),
    ("nogas",     "apt", "Electric only (no gas)", "yesno", "important", 3.0,
     "An induction hob, or 'w budynku nie ma gazu', means Yes.", None, None, True, True),
    ("modern",    "apt", "Modern — building feels new", "r3", "important", 3.0,
     "0 = tired old block, 3 = new build in great shape.", None, None, True, True),
    ("kitchen",   "apt", "Kitchen size", "r3", "important", 3.0, None, None, None, True, True),
    ("bed",       "apt", "Bed included", "yesno", "important", 2.0, None, None, None, True, True),
    ("newwin",    "apt", "New windows", "yesno", "important", 2.0, None, None, None, True, True),
    ("appliances","apt", "Appliances OK", "r3", "important", 2.0,
     "3 means fridge, washing machine and dishwasher are all present.",
     None, None, True, True),
    ("elevator",  "apt", "Lift OK / low floor", "yesno", "nice", 1.0, None, None, None, True, True),
    ("bike",      "apt", "Bike storage", "yesno", "nice", 1.0, None, None, None, True, False),
    ("wintercost","apt", "Winter heating zł/mo (info)", "num", "none", None, None, None, None, False, False),

    # --- contract ------------------------------------------------------------
    ("contract",  "contract", "Contract type", "enum", "important", 3.0, None,
     [{"value": "Standardowa", "points": 1}, {"value": "Okazjonalna", "points": 0}],
     None, True, False),
    ("play",      "contract", "Play internet available", "yesno", "nice", 1.0, None, None, None, True, False),
    ("furniture", "contract", "Furniture changes allowed", "r3", "nice", 1.0, None, None, None, True, False),

    # --- nice to have --------------------------------------------------------
    ("bathtub",   "nice", "Bathtub", "yesno", "nice", 1.0, None, None, None, True, True),
    ("wardrobe",  "nice", "Wardrobe", "yesno", "nice", 1.0, None, None, None, True, True),
    ("balcony",   "nice", "Balcony", "yesno", "nice", 1.0, None, None, None, True, True),
]

# Your own bookkeeping — a listing cannot tell the model whether you have
# messaged the landlord, and asking invites it to invent an answer.
NOT_SCRAPABLE = {"link", "messaged", "msgdate", "presched", "presdate", "notes"}

PLACES = [
    ("work", "Work", "ul. Lublańska 34A, Kraków", 5.0, 0,
     [{"mode": "BICYCLING", "share": 0.7, "full": 10, "zero": 30},
      {"mode": "TRANSIT", "share": 0.3, "full": 15, "zero": 40}]),
    ("gym", "Gym", "al. 29 Listopada 39F, 31-425 Kraków", 3.0, 1,
     [{"mode": "BICYCLING", "share": 0.7, "full": 12, "zero": 30},
      {"mode": "TRANSIT", "share": 0.3, "full": 18, "zero": 40}]),
    ("centre", "City centre", "Rynek Główny, Kraków", 2.0, 2,
     [{"mode": "BICYCLING", "share": 0.6, "full": 15, "zero": 40},
      {"mode": "TRANSIT", "share": 0.4, "full": 20, "zero": 45}]),
]

SETTINGS = {
    "budgetYear": 42500, "overPct": 0.05,
    "highThr": 0.75, "midThr": 0.60, "minData": 0.35,
    "moveInBy": "2026-09-01", "departHour": 10,
    "city": "Kraków", "region": "pl",
}


async def seed_user(session: AsyncSession, uid: str, email: str | None) -> bool:
    """Create the defaults for a user exactly once. Returns True if it seeded."""
    user = await session.get(User, uid)
    if user is None:
        user = User(uid=uid, email=email)
        session.add(user)
        await session.flush()
    if user.seeded:
        return False

    # Guard against a half-seeded state from an interrupted first run.
    existing = (await session.execute(
        select(Category.id).where(Category.uid == uid).limit(1))).first()
    if existing:
        user.seeded = True
        return False

    cats: dict[str, Category] = {}
    for key, title, color, sort in CATEGORIES:
        c = Category(uid=uid, key=key, title=title, color=color, sort=sort)
        session.add(c)
        cats[key] = c
    await session.flush()

    for i, (key, cat, label, kind, importance, wo, hint, options, config,
            scored, photo) in enumerate(CRITERIA):
        session.add(Criterion(
            uid=uid, category_id=cats[cat].id, key=key, label=label, kind=kind,
            importance=importance, weight_override=wo, hint=hint,
            options=options, config=config, scored=scored,
            photo_evidence=photo, scrapable=key not in NOT_SCRAPABLE,
            sort=i, builtin=True))

    for i, (key, name, address, weight, sort, modes) in enumerate(PLACES):
        session.add(Place(uid=uid, key=key, name=name, address=address,
                          weight=weight, sort=sort, modes=modes))

    for key, value in SETTINGS.items():
        session.add(Setting(uid=uid, key=key, value={"v": value}))

    user.seeded = True
    return True
