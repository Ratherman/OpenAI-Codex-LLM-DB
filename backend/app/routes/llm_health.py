from flask import Blueprint, current_app, jsonify

from app.services.llm_service import check_llm_health

llm_health_bp = Blueprint("llm_health", __name__)


@llm_health_bp.get("/api/llm/health")
def llm_health():
    result = check_llm_health(current_app.config["OPENAI_API_KEY"])

    if not result["configured"] or not result["api_reachable"]:
        return jsonify({"status": "error", **result}), 503

    return jsonify({"status": "ok", **result})
