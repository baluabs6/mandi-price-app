from flask import Blueprint, current_app, jsonify, request

from extensions import limiter
from services.rag import answer_question

assistant_bp = Blueprint("assistant", __name__, url_prefix="/api")

ALLOWED_LANGS = {"en", "hi", "te"}


@assistant_bp.route("/ask", methods=["POST"])
@limiter.limit("10 per minute")  # LLM calls are expensive — tighter limit than read endpoints
def ask():
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    lang = body.get("lang") if body.get("lang") in ALLOWED_LANGS else "en"

    if not question:
        return jsonify({"error": "question is required"}), 400
    if len(question) > 500:
        return jsonify({"error": "question is too long (max 500 characters)"}), 400

    result = answer_question(
        question,
        lang,
        api_key=current_app.config["ANTHROPIC_API_KEY"],
        model=current_app.config["ANTHROPIC_MODEL"],
    )
    result["assistant_enabled"] = current_app.config["ASSISTANT_ENABLED"]
    return jsonify(result)
