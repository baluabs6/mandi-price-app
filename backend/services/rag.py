"""Retrieval-augmented answering over the mandi price DB.

Deliberately rule-based retrieval (not vector search) — the schema is
small, structured, and low-cardinality (a few hundred crops/markets), so
fuzzy string matching against known names is more reliable and far
cheaper than embeddings for this dataset. If the catalog grows into the
thousands of distinct crop/variety names, swap `_match_entities` for a
proper embedding index without changing the route contract.
"""
from datetime import date, timedelta
from difflib import get_close_matches

from extensions import db
from models import Crop, District, Market, PriceRecord, State
from services.llm import LLMError, complete

SYSTEM_PROMPT = (
    "You are a plain-spoken assistant for Indian farmers checking mandi "
    "(market) crop prices. You are given real price records retrieved from "
    "a government price database (Agmarknet / data.gov.in). Answer only "
    "using the data provided — never invent a price, market, or trend that "
    "isn't in the given records. If the records don't cover what was asked, "
    "say so plainly. Keep answers short (2-4 sentences), concrete, and in "
    "the requested language. Always state prices in Rs per quintal and "
    "include the date the price is from."
)


def _match_entities(question: str):
    """Fuzzy-match crop/state/district names mentioned in the question
    against what's actually in the DB, so a misspelling like 'tomatoe'
    or a Hindi/Telugu name still resolves to a real filter."""
    q_lower = question.lower()

    crop = None
    for c in Crop.query.all():
        names = [n for n in (c.name_en, c.name_hi, c.name_te) if n]
        if any(n.lower() in q_lower for n in names):
            crop = c
            break
    if crop is None:
        words = q_lower.split()
        crop_names = {c.name_en.lower(): c for c in Crop.query.all()}
        for word in words:
            match = get_close_matches(word, crop_names.keys(), n=1, cutoff=0.8)
            if match:
                crop = crop_names[match[0]]
                break

    state = None
    for s in State.query.all():
        names = [n for n in (s.name_en, s.name_hi, s.name_te) if n]
        if any(n.lower() in q_lower for n in names):
            state = s
            break

    district = None
    d_query = District.query
    if state:
        d_query = d_query.filter_by(state_id=state.id)
    for d in d_query.all():
        names = [n for n in (d.name_en, d.name_hi, d.name_te) if n]
        if any(n.lower() in q_lower for n in names):
            district = d
            break

    return crop, state, district


def answer_question(question: str, lang: str, api_key: str, model: str) -> dict:
    """Returns {"answer": str, "matched": {...}, "records_used": int}."""
    crop, state, district = _match_entities(question)

    q = PriceRecord.query.join(Market).join(District).join(State)
    if crop:
        q = q.filter(PriceRecord.crop_id == crop.id)
    if district:
        q = q.filter(Market.district_id == district.id)
    elif state:
        q = q.filter(District.state_id == state.id)

    since = date.today() - timedelta(days=14)
    q = q.filter(PriceRecord.price_date >= since)
    records = q.order_by(PriceRecord.price_date.desc()).limit(30).all()

    if not records:
        return {
            "answer": _no_data_message(lang),
            "matched": {
                "crop": crop.name_en if crop else None,
                "state": state.name_en if state else None,
                "district": district.name_en if district else None,
            },
            "records_used": 0,
        }

    context_lines = [
        f"- {r.crop.name_en} at {r.market.name_en}, {r.market.district.name_en}: "
        f"modal Rs {r.modal_price}/quintal (min {r.min_price}, max {r.max_price}) on {r.price_date.isoformat()}"
        for r in records
    ]
    context = "\n".join(context_lines)
    lang_name = {"hi": "Hindi", "te": "Telugu", "en": "English"}.get(lang, "English")

    user_prompt = (
        f"Farmer's question: {question}\n\n"
        f"Respond in {lang_name}.\n\n"
        f"Retrieved price records (most recent 14 days, up to 30 rows):\n{context}"
    )

    try:
        answer = complete(SYSTEM_PROMPT, user_prompt, api_key=api_key, model=model)
    except LLMError:
        answer = _fallback_summary(records, lang)

    return {
        "answer": answer,
        "matched": {
            "crop": crop.name_en if crop else None,
            "state": state.name_en if state else None,
            "district": district.name_en if district else None,
        },
        "records_used": len(records),
    }


def _no_data_message(lang: str) -> str:
    return {
        "hi": "क्षमा करें, इस चयन के लिए हाल का कोई मूल्य डेटा नहीं मिला।",
        "te": "క్షమించండి, ఈ ఎంపికకు ఇటీవలి ధర డేటా కనుగొనబడలేదు.",
    }.get(lang, "Sorry, no recent price data was found for that selection.")


def _fallback_summary(records, lang: str) -> str:
    """If the LLM call fails (no API key, network error, etc.) still
    return something useful and clearly data-grounded, rather than an
    error. This is what the /api/ask endpoint returns when
    ASSISTANT_ENABLED is False but the endpoint is still called."""
    latest = records[0]
    return (
        f"Latest: {latest.crop.name_en} at {latest.market.name_en} — "
        f"Rs {latest.modal_price}/quintal on {latest.price_date.isoformat()} "
        f"(min {latest.min_price}, max {latest.max_price}). "
        f"[AI summary unavailable — showing raw latest record instead.]"
    )
