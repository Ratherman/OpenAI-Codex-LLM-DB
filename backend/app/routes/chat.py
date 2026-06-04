from flask import Blueprint, current_app, jsonify, request

from app.services.llm_service import generate_reply

chat_bp = Blueprint("chat", __name__)


@chat_bp.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    model = str(payload.get("model", "gpt-4o")).strip() or "gpt-4o"
    system_prompt = str(payload.get("systemPrompt", "")).strip()

    try:
        temperature = float(payload.get("temperature", 0.3))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "error": "temperature must be a number"}), 400

    temperature = max(0, min(1, temperature))

    if not message:
        return jsonify({"status": "error", "error": "message is required"}), 400

    try:
        result = generate_reply(
            api_key=current_app.config["OPENAI_API_KEY"],
            message=message,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
        )
    except Exception as exc:
        return (
            jsonify(
                {
                    "status": "error",
                    "error": str(exc),
                    "model": model,
                }
            ),
            502,
        )

    return jsonify({"status": "ok", **result})
