"""Grounded answering over the mandi price DB.

Two modes, tried in order:

1. **Tool use** (when an API key is configured) — the model is given a
   handful of read-only database tools (`services/tools.py`) and chooses
   which to call: best markets, latest prices, trend, anomalies,
   forecast. It can answer follow-up questions using recent chat turns.
   The tools reuse the same logic as the REST endpoints, so the assistant
   never computes or invents numbers itself.
2. **Rule-based retrieval** — fuzzy-match crop/state/district names in the
   question, fetch matching rows, and either have the LLM summarise them
   or (with no key / on LLM failure) return a plain "latest record"
   answer. This keeps the endpoint useful when the LLM is unavailable.

Retrieval is deliberately rule-based, not vector search — the schema is
small and low-cardinality (a few hundred crops/markets), so fuzzy string
matching against known names is more reliable and far cheaper than
embeddings. If the catalog grows into the thousands of distinct names,
swap `_match_entities` for an embedding index without changing the route
contract.
"""
import logging
from datetime import date, timedelta
from difflib import get_close_matches

from extensions import db
from models import Crop, District, Market, PriceRecord, State
from services.llm import LLMError, complete, complete_with_tools
from services.tools import TOOL_DEFINITIONS, ToolRunner, _record_summary

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 6
MAX_HISTORY_CHARS = 1000

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


TOOL_SYSTEM_PROMPT = (
    "You are a plain-spoken assistant for Indian farmers checking mandi "
    "(market) crop prices, backed by a government price database "
    "(Agmarknet / data.gov.in). Today's date is {today}. "
    "ALWAYS use the provided tools to look up prices, trends, anomalies or "
    "forecasts — never answer a price question from memory, and never invent "
    "a price, market, date or trend. If a tool returns no data or an error, "
    "say so plainly. Answer only from tool results. Keep answers short "
    "(2-4 sentences), concrete, and in {lang_name}. State prices in Rs per "
    "quintal and include the date of the price. For forecasts, say it is a "
    "directional estimate and mention the confidence. Use earlier turns of "
    "the conversation to resolve follow-ups like 'and in Warangal?'. If the "
    "question is not about crop prices, politely say you can only help with "
    "mandi prices."
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


def _clean_history(history):
    """Validate client-supplied chat history before it reaches the LLM:
    only user/assistant string turns, truncated, last N, strictly
    alternating, and starting with a user turn (an API requirement).
    The client is untrusted, so anything malformed is silently dropped."""
    cleaned = []
    for item in (history or [])[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        role, content = item.get("role"), item.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str) or not content.strip():
            continue
        if cleaned and cleaned[-1]["role"] == role:
            continue
        if not cleaned and role != "user":
            continue
        cleaned.append({"role": role, "content": content.strip()[:MAX_HISTORY_CHARS]})
    while cleaned and cleaned[-1]["role"] == "user":  # the new question is the next user turn
        cleaned.pop()
    return cleaned


def _lang_name(lang):
    return {"hi": "Hindi", "te": "Telugu", "en": "English"}.get(lang, "English")


def _matched_dict(crop, state, district):
    return {
        "crop": crop.name_en if crop else None,
        "state": state.name_en if state else None,
        "district": district.name_en if district else None,
    }


def _answer_with_tools(question, lang, history, api_key, model, matched):
    runner = ToolRunner()
    system = TOOL_SYSTEM_PROMPT.format(today=date.today().isoformat(), lang_name=_lang_name(lang))
    messages = _clean_history(history) + [{"role": "user", "content": question}]
    answer = complete_with_tools(
        system, messages, TOOL_DEFINITIONS, runner, api_key=api_key, model=model
    )
    sources = runner.source_list()
    return {
        "answer": answer,
        "matched": matched,
        "records_used": len(runner.sources),
        "sources": sources,
        "mode": "tools",
    }


def answer_question(question: str, lang: str, api_key: str, model: str, history=None) -> dict:
    """Returns {"answer", "matched", "records_used", "sources", "mode"}.

    `mode` is "tools", "retrieval" (LLM summarised retrieved rows) or
    "fallback" (no LLM available — plain latest-record answer).
    """
    crop, state, district = _match_entities(question)
    matched = _matched_dict(crop, state, district)

    llm_failed = False
    if api_key:
        try:
            return _answer_with_tools(question, lang, history, api_key, model, matched)
        except LLMError:
            llm_failed = True
            logger.warning("Tool-use answer failed; degrading to retrieval path")

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
            "matched": matched,
            "records_used": 0,
            "sources": [],
            "mode": "fallback",
        }

    sources = [_record_summary(r) for r in records[:10]]
    context_lines = [
        f"- {r.crop.name_en} at {r.market.name_en}, {r.market.district.name_en}: "
        f"modal Rs {r.modal_price}/quintal (min {r.min_price}, max {r.max_price}) on {r.price_date.isoformat()}"
        for r in records
    ]
    context = "\n".join(context_lines)

    user_prompt = (
        f"Farmer's question: {question}\n\n"
        f"Respond in {_lang_name(lang)}.\n\n"
        f"Retrieved price records (most recent 14 days, up to 30 rows):\n{context}"
    )

    mode = "retrieval"
    answer = None
    if api_key and not llm_failed:
        try:
            answer = complete(SYSTEM_PROMPT, user_prompt, api_key=api_key, model=model)
        except LLMError:
            answer = None
    if not answer:
        answer = _fallback_summary(records, lang)
        mode = "fallback"

    return {
        "answer": answer,
        "matched": matched,
        "records_used": len(records),
        "sources": sources,
        "mode": mode,
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
