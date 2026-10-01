import hashlib

from flask import Blueprint, current_app, jsonify, request

from extensions import cache, limiter
from services.rag import answer_question

assistant_bp = Blueprint("assistant", __name__, url_prefix="/api")

ALLOWED_LANGS = {"en", "hi", "te"}
ANSWER_CACHE_SECONDS = 15 * 60  # prices refresh ~daily, so a short cache is safe


def _answer_cache_key(question, lang):
    digest = hashlib.sha256(f"{lang}|{question.lower()}".encode("utf-8")).hexdigest()
    return f"ask:{digest}"


@assistant_bp.route("/ask", methods=["POST"])
# LLM calls are expensive — tighter limits than read endpoints, plus a daily
# per-IP ceiling so one client can't run up the Anthropic bill.
@limiter.limit("10 per minute;100 per day")
def ask():
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    lang = body.get("lang") if body.get("lang") in ALLOWED_LANGS else "en"
    history = body.get("history")

    if not question:
        return jsonify({"error": "question is required"}), 400
    if len(question) > 500:
        return jsonify({"error": "question is too long (max 500 characters)"}), 400
    if history is not None and not isinstance(history, list):
        return jsonify({"error": "history must be a list of {role, content} messages"}), 400

    # Only standalone questions are cached: a follow-up like "and in
    # Warangal?" means something different depending on earlier turns.
    cache_key = None if history else _answer_cache_key(question, lang)
    if cache_key:
        cached = cache.get(cache_key)
        if cached:
            cached = dict(cached)
            cached["assistant_enabled"] = current_app.config["ASSISTANT_ENABLED"]
            return jsonify(cached)

    result = answer_question(
        question,
        lang,
        api_key=current_app.config["ANTHROPIC_API_KEY"],
        model=current_app.config["ANTHROPIC_MODEL"],
        history=history,
    )

    # Don't cache degraded answers — let the next request retry the LLM.
    if cache_key and result.get("mode") in ("tools", "retrieval"):
        cache.set(cache_key, result, timeout=ANSWER_CACHE_SECONDS)

    result["assistant_enabled"] = current_app.config["ASSISTANT_ENABLED"]
    return jsonify(result)
