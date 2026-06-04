from flask import Blueprint, jsonify, request

chat_bp = Blueprint("chat", __name__)


@chat_bp.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    model = str(payload.get("model", "gpt-4o")).strip() or "gpt-4o"

    if not message:
        return jsonify({"status": "error", "error": "message is required"}), 400

    return jsonify(
        {
            "status": "ok",
            "provider": "mock",
            "model": model,
            "message": f"後端已收到你的訊息：{message}。下一階段會由 LLM 回覆。",
        }
    )
