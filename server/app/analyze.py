"""Three passes over a listing: text, photos, then reconciliation.

Each pass is forced through a tool schema, so the reply is always an object of
the exact shape we asked for — no prose, no markdown fences, no invented keys.
"""
from __future__ import annotations

import base64
import json
import logging

from anthropic import AsyncAnthropic

from . import schema

log = logging.getLogger("analyze")

SYSTEM = (
    "You extract structured facts about rental flats from Polish listing pages for a "
    "prospective tenant in Kraków.\n\n"
    "Rules that matter more than completeness:\n"
    "· Null is a valid, useful answer. If the listing does not say and you cannot see it, "
    "return null. A confident wrong value is far worse than a null, because it silently "
    "changes the tenant's ranking.\n"
    "· Never infer a 'No' from silence. A listing that fails to mention a bathtub is null, "
    "not No. Only answer No when something is stated or visible to be absent.\n"
    "· Polish specifics: 'czynsz' is the administrative rent, separate from the rent itself. "
    "'kaucja' is the deposit. 'prowizja' is the agency fee. 'od zaraz' means available "
    "immediately. 'kawalerka' is a studio. 'umowa okazjonalna' is the occasional-tenancy "
    "contract, 'standardowa' the normal one.\n"
    "· Confidence should reflect evidence, not eagerness: 1.0 when it is stated outright, "
    "around 0.5 for a reasonable reading, below 0.3 for a guess.\n"
    "· Evidence must be a short quote or a concrete visual detail, never a restatement of "
    "your answer."
)


def _tool(ls, keys, name, desc):
    return {
        "name": name,
        "description": desc,
        "input_schema": ls.json_schema(keys, with_confidence=True),
    }


async def _call(client, model, tool, blocks, max_tokens=4096):
    msg = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM,
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},  # forces the schema
        messages=[{"role": "user", "content": blocks}],
    )
    for block in msg.content:
        if block.type == "tool_use":
            return block.input, msg.usage
    raise RuntimeError("model did not return the structured result")


async def pass_text(client, model, listing: dict, ls) -> tuple[dict, object]:
    keys = ls.all_keys
    tool = _tool(ls, keys, "record_listing_facts",
                 "Record what the listing text states about the flat.")
    meta = json.dumps(listing.get("meta") or {}, ensure_ascii=False, indent=1)[:4000]
    prompt = (
        f"Listing title: {listing.get('title') or '(none)'}\n"
        f"Source: {listing.get('source')}\n\n"
        f"Structured fields the site exposed:\n{meta}\n\n"
        f"Description text:\n---\n{listing.get('text') or '(empty)'}\n---\n\n"
        "Fill in every field from the text and structured fields above. You are working "
        "from words only — no photographs. For anything the text does not support, return "
        "null with confidence 0.\n\n"
        f"Field notes:\n{ls.spec(keys)}"
    )
    return await _call(client, model, tool, [{"type": "text", "text": prompt}])


async def pass_photos(client, model, photos: list[dict], listing: dict, ls) -> tuple[dict, object]:
    keys = ls.photo_keys
    tool = _tool(ls, keys, "record_photo_findings",
                 "Record only what is visible in the photographs.")
    blocks = []
    for i, p in enumerate(photos, 1):
        blocks.append({"type": "text", "text": f"Photo {i}:"})
        blocks.append({"type": "image", "source": {
            "type": "base64", "media_type": p["media_type"],
            "data": base64.b64encode(p["data"]).decode(),
        }})
    blocks.append({"type": "text", "text": (
        f"These are the {len(photos)} photographs from a rental listing"
        f"{' titled ' + listing['title'] if listing.get('title') else ''}.\n\n"
        "Judge only from what you can see. Do not use any assumption about what such a "
        "listing usually says — you have not been shown the description on purpose.\n\n"
        "Look specifically for: whether there is a bedroom separate from the living area; "
        "clear floor space for a 140x90 cm desk and a 120x50 cm digital piano; window size "
        "and how much daylight reaches the rooms; kitchen size and whether it is separate; "
        "hob type, since an induction or ceramic hob means no gas; visible damp, mould or "
        "stained corners; window frames and whether they look recent; a bathtub as opposed "
        "to only a shower; wardrobes or built-in storage; a balcony; the general age and "
        "condition of the building and finishes.\n\n"
        f"Field notes:\n{ls.spec(keys)}"
    )})
    return await _call(client, model, tool, blocks)


async def pass_reconcile(client, model, text_res: dict, photo_res: dict,
                         listing: dict, ls) -> tuple[dict, object]:
    keys = ls.all_keys
    tool = _tool(ls, keys, "record_final_answer",
                 "The final value for each field, having weighed text against photos.")

    def brief(d):
        return json.dumps({k: v for k, v in (d or {}).items()},
                          ensure_ascii=False, indent=1)[:8000]

    prompt = (
        "Two independent passes over the same listing. The first read only the text, the "
        "second saw only the photographs.\n\n"
        f"From the text:\n{brief(text_res)}\n\n"
        f"From the photographs:\n{brief(photo_res)}\n\n"
        "Produce the final answer for every field.\n\n"
        "How to weigh them:\n"
        "· Prices, dates, contract terms and anything administrative: trust the text. A "
        "photograph cannot show a deposit.\n"
        "· Condition, light, space, layout, fittings: trust the photographs where they "
        "disagree with the text. Listings describe a 'jasne, przestronne' flat regardless "
        "of what it looks like; the photographs do not flatter.\n"
        "· Where both agree, raise the confidence above either alone.\n"
        "· Where they conflict and neither is clearly better placed to know, prefer the "
        "more conservative value and say so in the evidence.\n"
        "· A field null in both stays null. Do not fill gaps by reasoning about what is "
        "likely — the tenant would rather see a blank and go and look.\n\n"
        f"Field notes:\n{ls.spec(keys)}"
    )
    return await _call(client, model, tool, [{"type": "text", "text": prompt}], max_tokens=6000)


def tidy(raw: dict, ls) -> dict:
    """Validate and flatten {key: {value, confidence, evidence}} for the browser."""
    out = {}
    for k, v in (raw or {}).items():
        if k not in ls.by_key:
            continue
        if isinstance(v, dict):
            val = ls.coerce(k, v.get("value"))
            out[k] = {"value": val,
                      "confidence": None if val is None else v.get("confidence"),
                      "evidence": None if val is None else (v.get("evidence") or None)}
        else:
            val = ls.coerce(k, v)
            out[k] = {"value": val, "confidence": None, "evidence": None}
    return out


def usage_sum(*usages):
    ins = sum(getattr(u, "input_tokens", 0) or 0 for u in usages if u)
    outs = sum(getattr(u, "output_tokens", 0) or 0 for u in usages if u)
    return {"input_tokens": ins, "output_tokens": outs}


def client_for(key: str) -> AsyncAnthropic:
    return AsyncAnthropic(api_key=key)
