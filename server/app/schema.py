"""The fields the model is asked to extract.

These keys must match the form fields in index.html exactly — the frontend
writes whatever comes back straight onto the candidate object.

`kind` drives both the prompt wording and the validation:
    num    - a plain number
    yesno  - "Yes" / "No"
    r3     - "0".."3" subjective rating
    enum   - one of `options`
    date   - ISO yyyy-mm-dd
    text   - free text
"""

FIELDS = [
    # --- money and size -----------------------------------------------------
    dict(key="rent", kind="num", label="Base monthly rent (najem) in PLN",
         hint="The headline rent only, excluding czynsz and utilities."),
    dict(key="admin", kind="num", label="Monthly administrative rent (czynsz administracyjny) in PLN",
         hint="Often listed as 'czynsz' or 'czynsz administracyjny'. Not the same as rent."),
    dict(key="util", kind="num", label="Estimated monthly utilities (media: prąd, gaz, woda) in PLN",
         hint="Only if stated or clearly derivable. Do not invent a figure."),
    dict(key="kaucja", kind="num", label="Deposit (kaucja) in PLN"),
    dict(key="provision", kind="num", label="One-off agency provision (prowizja) in PLN",
         hint="If it is described as one month's rent, use the rent value."),
    dict(key="wintercost", kind="num", label="Typical winter heating cost per month in PLN"),
    dict(key="area", kind="num", label="Floor area in square metres"),

    # --- identity -----------------------------------------------------------
    dict(key="address", kind="text",
         label="Street address or the most precise location given, plus district"),
    dict(key="availfrom", kind="date", label="Date the flat becomes available",
         hint="'od zaraz' / 'available immediately' means today's date. Only use a date "
              "tied to availability wording, never a date mentioned for another reason "
              "such as a new tram line opening."),

    # --- neighbourhood ------------------------------------------------------
    dict(key="chain", kind="enum", label="Nearest grocery chain",
         options=["Lidl", "Auchan", "Netto", "Biedronka", "Lewiatan", "Other", "None nearby"]),
    dict(key="grocmin", kind="num", label="Walking minutes to the nearest grocery shop"),
    dict(key="transmin", kind="num", label="Walking minutes to the nearest public transport stop"),
    dict(key="parkmin", kind="num", label="Walking minutes to the nearest park"),
    dict(key="windows", kind="enum", label="Direction the windows face",
         options=["East", "East–North", "North", "North–West", "South–East", "South",
                  "West", "Other / unknown"]),
    dict(key="quiet", kind="r3", label="How quiet the surroundings are",
         hint="0 busy road or nightlife, 3 clearly quiet residential."),
    dict(key="neighbors", kind="r3", label="How calm the neighbours sound"),

    # --- the flat -----------------------------------------------------------
    dict(key="bedroom", kind="yesno", label="Has a separate bedroom",
         hint="A studio or 'kawalerka' is No. '2 pokoje' with a kitchen annexe usually means "
              "a living room plus a separate bedroom, which is Yes."),
    dict(key="heating", kind="yesno", label="Has district / central heating (ogrzewanie miejskie)"),
    dict(key="nogas", kind="yesno", label="Electric only, no gas in the flat or building",
         hint="An induction hob, or 'w budynku nie ma gazu', means Yes."),
    dict(key="desk", kind="yesno", label="There is room for a 140x90 cm desk"),
    dict(key="piano", kind="yesno", label="There is room for a 120x50 cm digital piano"),
    dict(key="bed", kind="yesno", label="A bed is included"),
    dict(key="newwin", kind="yesno", label="Windows look new and well insulating"),
    dict(key="nomold", kind="yesno", label="No sign of damp or mould",
         hint="Only answer No on visible evidence. Absence of evidence is null, not Yes."),
    dict(key="elevator", kind="yesno", label="Has a working lift, or is on a low floor"),
    dict(key="bike", kind="yesno", label="Has dedicated bicycle storage"),
    dict(key="bathtub", kind="yesno", label="The bathroom has a bathtub, not only a shower"),
    dict(key="wardrobe", kind="yesno", label="Has a wardrobe or built-in storage"),
    dict(key="balcony", kind="yesno", label="Has a balcony, loggia or terrace"),
    dict(key="modern", kind="r3", label="How modern and well kept the building and flat feel",
         hint="0 tired old block, 3 new build in excellent condition."),
    dict(key="kitchen", kind="r3", label="Kitchen size and usability",
         hint="0 a token annexe, 3 a generous separate kitchen."),
    dict(key="sun", kind="r3", label="How much natural light the flat gets"),
    dict(key="appliances", kind="r3", label="Coverage of fridge, washing machine and dishwasher",
         hint="3 means all three are present."),

    # --- contract -----------------------------------------------------------
    dict(key="contract", kind="enum", label="Contract type",
         options=["Standardowa", "Okazjonalna"]),
    dict(key="play", kind="yesno", label="Play is available as an internet provider"),
    dict(key="furniture", kind="r3", label="How much freedom there is to change the furniture"),
]

BY_KEY = {f["key"]: f for f in FIELDS}

# Which fields a photo can honestly speak to. Asking the vision pass about the
# deposit produces confident nonsense, so it is simply not offered those.
PHOTO_FIELDS = [
    "bedroom", "desk", "piano", "bed", "newwin", "nomold", "bathtub", "wardrobe",
    "balcony", "modern", "kitchen", "sun", "appliances", "elevator", "nogas", "area",
]

TEXT_ONLY = [f["key"] for f in FIELDS if f["key"] not in PHOTO_FIELDS]


def field_spec(keys):
    """Compact, promptable description of the requested fields."""
    out = []
    for k in keys:
        f = BY_KEY[k]
        line = f'- "{k}" ({f["kind"]}'
        if f["kind"] == "enum":
            line += ": one of " + " | ".join(f["options"])
        line += f'): {f["label"]}'
        if f.get("hint"):
            line += f' — {f["hint"]}'
        out.append(line)
    return "\n".join(out)


def json_schema(keys, with_confidence=True):
    """A JSON Schema for the requested fields.

    Passed to the API as a tool `input_schema` with tool_choice forcing that
    tool, so the model cannot reply with prose, markdown fences or a differently
    shaped object. Every field is nullable — "I could not tell" has to be
    expressible, otherwise the model invents an answer to satisfy the schema.
    """
    props = {}
    for k in keys:
        f = BY_KEY[k]
        kind = f["kind"]
        if kind == "num":
            val = {"type": ["number", "null"]}
        elif kind == "yesno":
            val = {"type": ["string", "null"], "enum": ["Yes", "No", None]}
        elif kind == "r3":
            val = {"type": ["string", "null"], "enum": ["0", "1", "2", "3", None]}
        elif kind == "enum":
            val = {"type": ["string", "null"], "enum": f["options"] + [None]}
        elif kind == "date":
            val = {"type": ["string", "null"],
                   "description": "ISO date, yyyy-mm-dd"}
        else:
            val = {"type": ["string", "null"]}
        val["description"] = f["label"] + (f" — {f['hint']}" if f.get("hint") else "")

        if with_confidence:
            props[k] = {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "value": val,
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1,
                                   "description": "0 = guess, 1 = stated outright."},
                    "evidence": {"type": ["string", "null"], "maxLength": 240,
                                 "description": "The quote or the image detail this came "
                                                "from. Null when the value is null."},
                },
                "required": ["value", "confidence", "evidence"],
            }
        else:
            props[k] = val

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": props,
        "required": list(keys),
    }


def coerce(key, value):
    """Return a validated value or None. The frontend trusts what we send."""
    if value is None:
        return None
    f = BY_KEY.get(key)
    if not f:
        return None
    kind = f["kind"]
    if isinstance(value, str) and value.strip().lower() in ("", "null", "none", "unknown", "n/a"):
        return None
    try:
        if kind == "num":
            v = float(str(value).replace(" ", "").replace(",", "."))
            return None if v < 0 else round(v, 2)
        if kind == "yesno":
            s = str(value).strip().lower()
            if s in ("yes", "true", "tak", "1"):
                return "Yes"
            if s in ("no", "false", "nie", "0"):
                return "No"
            return None
        if kind == "r3":
            v = int(round(float(value)))
            return str(v) if 0 <= v <= 3 else None
        if kind == "enum":
            s = str(value).strip()
            for o in f["options"]:
                if o.lower() == s.lower():
                    return o
            return None
        if kind == "date":
            s = str(value).strip()[:10]
            import re
            return s if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) else None
        return str(value).strip() or None
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# Live schema from the database.
#
# FIELDS above is the fallback used when nothing has been configured. Once a
# user has criteria in Postgres, the scraper asks about *those* — so a criterion
# added in the admin panel is extracted from the next listing without a deploy.
# --------------------------------------------------------------------------

# Kinds the model can meaningfully answer. A calc field is derived, and a
# textarea is free-form notes; neither belongs in an extraction schema.
EXTRACTABLE_KINDS = {"num", "yesno", "r3", "enum", "date", "text"}


def fields_from_db(criteria: list) -> list[dict]:
    """Turn Criterion rows into the dicts the prompt builders expect."""
    out = []
    for c in criteria:
        if c.archived or not c.scrapable:
            continue
        kind = c.kind
        if kind in ("budget", "distance"):
            kind = "num"
        if kind not in EXTRACTABLE_KINDS:
            continue
        f = {"key": c.key, "kind": kind, "label": c.label}
        if c.hint:
            f["hint"] = c.hint
        if kind == "enum":
            f["options"] = [o.get("value") for o in (c.options or []) if o.get("value")]
            if not f["options"]:
                continue
        f["photo"] = bool(c.photo_evidence)
        out.append(f)
    return out


class LiveSchema:
    """Per-request view of the field set, so nothing global is mutated."""

    def __init__(self, fields: list[dict] | None = None):
        self.fields = fields or FIELDS
        self.by_key = {f["key"]: f for f in self.fields}
        self.photo_keys = [f["key"] for f in self.fields
                           if f.get("photo", f["key"] in PHOTO_FIELDS)]
        self.all_keys = [f["key"] for f in self.fields]

    def spec(self, keys):
        out = []
        for k in keys:
            f = self.by_key[k]
            line = f'- "{k}" ({f["kind"]}'
            if f["kind"] == "enum":
                line += ": one of " + " | ".join(f["options"])
            line += f'): {f["label"]}'
            if f.get("hint"):
                line += f' — {f["hint"]}'
            out.append(line)
        return "\n".join(out)

    def json_schema(self, keys, with_confidence=True):
        saved = dict(BY_KEY)
        try:
            BY_KEY.update(self.by_key)
            return json_schema(keys, with_confidence)
        finally:
            BY_KEY.clear()
            BY_KEY.update(saved)

    def coerce(self, key, value):
        saved = dict(BY_KEY)
        try:
            BY_KEY.update(self.by_key)
            return coerce(key, value)
        finally:
            BY_KEY.clear()
            BY_KEY.update(saved)
