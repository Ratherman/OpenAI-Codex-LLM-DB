import json
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_session
from app.models import ChatMessage, ChatRoom
from app.services.db_write_service import DbWriteError, confirm_db_write, prepare_db_write
from app.services.llm_service import MissingOpenAIKeyError, generate_reply, sanitize_error
from app.services.rag_service import DEFAULT_TOP_K, RagError, run_rag
from app.services.router_service import ROUTE_CAPABILITIES, RouterDecision, normalize_route, route_message
from app.services.sql_agent_service import SqlAgentError, run_sql_agent

chat_rooms_bp = Blueprint("chat_rooms", __name__)


def parse_metadata(metadata_json):
    try:
        return json.loads(metadata_json or "{}")
    except json.JSONDecodeError:
        return {"raw": metadata_json}


def serialize_room(room, message_count=None):
    return {
        "id": room.id,
        "title": room.title,
        "created_at": room.created_at.isoformat(),
        "updated_at": room.updated_at.isoformat(),
        "message_count": message_count,
    }


def serialize_message(message):
    return {
        "id": message.id,
        "room_id": message.room_id,
        "role": message.role,
        "content": message.content,
        "metadata": parse_metadata(message.metadata_json),
        "metadata_json": message.metadata_json,
        "created_at": message.created_at.isoformat(),
    }


def get_room_or_404(session, room_id):
    room = session.get(ChatRoom, room_id)
    if not room:
        return None, (jsonify({"status": "error", "error": "chat room not found"}), 404)
    return room, None


def parse_bool(payload, key, default=False):
    value = payload.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def serialize_router_decision(decision):
    return decision.model_dump() if decision else None


def parse_router_decision_from_payload(payload):
    raw_decision = payload.get("routerResult") or payload.get("router")
    if not raw_decision:
        return None

    try:
        return RouterDecision.model_validate(raw_decision)
    except Exception:
        return None


def build_selected_router_decision(payload, content, model, api_key):
    confirmed_route = payload.get("confirmedRoute") or payload.get("selectedRoute")
    existing_decision = parse_router_decision_from_payload(payload)

    if confirmed_route:
        selected_route = normalize_route(confirmed_route)
        data = (
            existing_decision.model_dump()
            if existing_decision
            else {
                "confidence": 1,
                "reason": "使用者手動選擇 route。",
                "suggested_followup_question": None,
            }
        )
        data["route"] = selected_route
        data["required_capability"] = ROUTE_CAPABILITIES[selected_route]
        return RouterDecision.model_validate(data)

    return existing_decision or route_message(api_key=api_key, message=content, model=model)


def get_route_gate_message(route, payload):
    if route == "general_chat":
        return None

    if route == "db_query" and not parse_bool(payload, "enableDbQuery", False):
        return "DB Query 尚未啟用，請先在右側開啟。"

    if route in {"db_query", "db_write"}:
        return None

    if route == "rag" and not parse_bool(payload, "enableRag", False):
        return "RAG 尚未啟用，請先在右側開啟。"

    if route == "image_skill" and not parse_bool(payload, "enableImageSkill", False):
        return "Image Skill 尚未啟用，請先在右側開啟。"

    return "此能力將在下一階段啟用。"


def get_route_gate_message(route, payload):
    if route == "general_chat":
        return None

    if route == "db_query" and not parse_bool(payload, "enableDbQuery", False):
        return "DB Query 尚未啟用，請先在右側開啟。"

    if route == "rag" and not parse_bool(payload, "enableRag", False):
        return "RAG 尚未啟用，請先在右側開啟。"

    if route in {"db_query", "db_write", "rag"}:
        return None

    if route == "image_skill" and not parse_bool(payload, "enableImageSkill", False):
        return "Image Skill 尚未啟用，請先在右側開啟。"

    return "此能力將在下一階段啟用。"


def make_assistant_message(room_id, content, metadata):
    return ChatMessage(
        room_id=room_id,
        role="assistant",
        content=content,
        metadata_json=json.dumps(metadata, ensure_ascii=False),
    )


def get_pending_write_message_or_404(session, room_id, message_id):
    message = session.get(ChatMessage, message_id)
    if not message or message.room_id != room_id or message.role != "assistant":
        return None, (jsonify({"status": "error", "error": "pending write message not found"}), 404)

    metadata = parse_metadata(message.metadata_json)
    pending_write = metadata.get("db_write")
    if not pending_write:
        return None, (jsonify({"status": "error", "error": "message does not contain pending db write"}), 400)

    return (message, metadata, pending_write), None


@chat_rooms_bp.post("/api/chat/rooms")
def create_chat_room():
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()

    session = get_session()
    try:
        if not title:
            count = session.execute(select(func.count()).select_from(ChatRoom)).scalar_one()
            title = f"聊天室 {count + 1}"

        room = ChatRoom(title=title)
        session.add(room)
        session.commit()

        return jsonify({"status": "ok", "room": serialize_room(room, 0)}), 201
    except SQLAlchemyError as exc:
        session.rollback()
        return jsonify({"status": "error", "error": str(exc)}), 500
    finally:
        session.close()


@chat_rooms_bp.get("/api/chat/rooms")
def list_chat_rooms():
    session = get_session()
    try:
        message_counts = (
            select(ChatMessage.room_id, func.count(ChatMessage.id).label("message_count"))
            .group_by(ChatMessage.room_id)
            .subquery()
        )
        rows = session.execute(
            select(ChatRoom, func.coalesce(message_counts.c.message_count, 0))
            .outerjoin(message_counts, ChatRoom.id == message_counts.c.room_id)
            .order_by(ChatRoom.updated_at.desc(), ChatRoom.id.desc())
        ).all()

        return jsonify(
            {
                "status": "ok",
                "rooms": [serialize_room(room, int(message_count)) for room, message_count in rows],
            }
        )
    except SQLAlchemyError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500
    finally:
        session.close()


@chat_rooms_bp.patch("/api/chat/rooms/<int:room_id>")
def update_chat_room(room_id):
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()

    if not title:
        return jsonify({"status": "error", "error": "title is required"}), 400

    session = get_session()
    try:
        room, error_response = get_room_or_404(session, room_id)
        if error_response:
            return error_response

        room.title = title
        room.updated_at = datetime.utcnow()
        session.commit()

        count = session.execute(
            select(func.count()).select_from(ChatMessage).where(ChatMessage.room_id == room.id)
        ).scalar_one()
        return jsonify({"status": "ok", "room": serialize_room(room, count)})
    except SQLAlchemyError as exc:
        session.rollback()
        return jsonify({"status": "error", "error": str(exc)}), 500
    finally:
        session.close()


@chat_rooms_bp.delete("/api/chat/rooms/<int:room_id>")
def delete_chat_room(room_id):
    session = get_session()
    try:
        room, error_response = get_room_or_404(session, room_id)
        if error_response:
            return error_response

        session.delete(room)
        session.commit()
        return jsonify({"status": "ok", "deleted_room_id": room_id})
    except SQLAlchemyError as exc:
        session.rollback()
        return jsonify({"status": "error", "error": str(exc)}), 500
    finally:
        session.close()


@chat_rooms_bp.get("/api/chat/rooms/<int:room_id>/messages")
def list_chat_room_messages(room_id):
    session = get_session()
    try:
        room, error_response = get_room_or_404(session, room_id)
        if error_response:
            return error_response

        messages = session.execute(
            select(ChatMessage).where(ChatMessage.room_id == room.id).order_by(ChatMessage.created_at, ChatMessage.id)
        ).scalars()
        return jsonify(
            {
                "status": "ok",
                "room": serialize_room(room),
                "messages": [serialize_message(message) for message in messages],
            }
        )
    except SQLAlchemyError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500
    finally:
        session.close()


@chat_rooms_bp.post("/api/chat/rooms/<int:room_id>/route")
def route_chat_room_message(room_id):
    payload = request.get_json(silent=True) or {}
    content = str(payload.get("message", "")).strip()
    model = str(payload.get("model", "gpt-4o")).strip() or "gpt-4o"

    if not content:
        return jsonify({"status": "error", "error": "message is required"}), 400

    session = get_session()
    try:
        room, error_response = get_room_or_404(session, room_id)
        if error_response:
            return error_response

        decision = route_message(
            api_key=current_app.config["OPENAI_API_KEY"],
            message=content,
            model=model,
        )
        return jsonify(
            {
                "status": "ok",
                "room": serialize_room(room),
                "router": serialize_router_decision(decision),
            }
        )
    except SQLAlchemyError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500
    finally:
        session.close()


@chat_rooms_bp.post("/api/chat/rooms/<int:room_id>/db-write/confirm")
def confirm_chat_room_db_write(room_id):
    payload = request.get_json(silent=True) or {}
    message_id = payload.get("messageId")

    if not message_id:
        return jsonify({"status": "error", "error": "messageId is required"}), 400

    session = get_session()
    try:
        room, error_response = get_room_or_404(session, room_id)
        if error_response:
            return error_response

        result_tuple, pending_error = get_pending_write_message_or_404(session, room.id, int(message_id))
        if pending_error:
            return pending_error

        pending_message, pending_metadata, pending_write = result_tuple
        result = confirm_db_write(session, pending_write, actor="frontend_user")

        pending_write["status"] = "confirmed"
        pending_write["record_id"] = result["record_id"]
        pending_write["audit_log_id"] = result["audit_log_id"]
        pending_metadata["db_write"] = pending_write
        pending_message.metadata_json = json.dumps(pending_metadata, ensure_ascii=False)

        success_message = make_assistant_message(
            room.id,
            result["message"],
            {
                "provider": "db_write_agent",
                "selected_route": "db_write",
                "db_write": result,
                "source": "db_write_confirm",
            },
        )
        room.updated_at = datetime.utcnow()
        session.add(success_message)
        session.commit()

        return jsonify(
            {
                "status": "ok",
                "messages": [serialize_message(pending_message), serialize_message(success_message)],
                "db_write": result,
            }
        )
    except (DbWriteError, ValueError) as exc:
        session.rollback()
        return jsonify({"status": "error", "error": str(exc)}), 400
    except SQLAlchemyError:
        session.rollback()
        return jsonify({"status": "error", "error": "資料庫寫入失敗，請確認資料是否重複或格式正確。"}), 500
    finally:
        session.close()


@chat_rooms_bp.post("/api/chat/rooms/<int:room_id>/db-write/cancel")
def cancel_chat_room_db_write(room_id):
    payload = request.get_json(silent=True) or {}
    message_id = payload.get("messageId")

    if not message_id:
        return jsonify({"status": "error", "error": "messageId is required"}), 400

    session = get_session()
    try:
        room, error_response = get_room_or_404(session, room_id)
        if error_response:
            return error_response

        result_tuple, pending_error = get_pending_write_message_or_404(session, room.id, int(message_id))
        if pending_error:
            return pending_error

        pending_message, pending_metadata, pending_write = result_tuple
        pending_write["status"] = "canceled"
        pending_metadata["db_write"] = pending_write
        pending_message.metadata_json = json.dumps(pending_metadata, ensure_ascii=False)

        cancel_message = make_assistant_message(
            room.id,
            "已取消這次資料寫入，資料庫沒有新增任何資料。",
            {
                "provider": "db_write_agent",
                "selected_route": "db_write",
                "db_write": {
                    "status": "canceled",
                    "tool": pending_write.get("tool"),
                },
                "source": "db_write_cancel",
            },
        )
        room.updated_at = datetime.utcnow()
        session.add(cancel_message)
        session.commit()

        return jsonify(
            {
                "status": "ok",
                "messages": [serialize_message(pending_message), serialize_message(cancel_message)],
            }
        )
    except (ValueError, SQLAlchemyError) as exc:
        session.rollback()
        return jsonify({"status": "error", "error": str(exc)}), 500
    finally:
        session.close()


@chat_rooms_bp.post("/api/chat/rooms/<int:room_id>/messages")
def create_chat_room_message(room_id):
    payload = request.get_json(silent=True) or {}
    content = str(payload.get("message", "")).strip()
    model = str(payload.get("model", "gpt-4o")).strip() or "gpt-4o"
    system_prompt = str(payload.get("systemPrompt", "")).strip()

    try:
        temperature = float(payload.get("temperature", 0.3))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "error": "temperature must be a number"}), 400

    temperature = max(0, min(1, temperature))

    try:
        memory_rounds = int(payload.get("memoryRounds", 5))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "error": "memoryRounds must be an integer"}), 400

    memory_rounds = max(1, min(10, memory_rounds))

    try:
        rag_top_k = int(payload.get("ragTopK", DEFAULT_TOP_K))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "error": "ragTopK must be an integer"}), 400

    rag_top_k = max(1, min(5, rag_top_k))
    enable_context_router = parse_bool(payload, "enableContextRouter", False)
    auto_route = parse_bool(payload, "autoRoute", True)
    router_decision = None
    selected_route = "general_chat"

    if not content:
        return jsonify({"status": "error", "error": "message is required"}), 400

    session = get_session()
    try:
        room, error_response = get_room_or_404(session, room_id)
        if error_response:
            return error_response

        if enable_context_router:
            router_decision = build_selected_router_decision(
                payload=payload,
                content=content,
                model=model,
                api_key=current_app.config["OPENAI_API_KEY"],
            )
            selected_route = router_decision.route

        history = list(
            session.execute(
                select(ChatMessage)
                .where(ChatMessage.room_id == room.id)
                .order_by(ChatMessage.created_at, ChatMessage.id)
            ).scalars()
        )
        user_message = ChatMessage(
            room_id=room.id,
            role="user",
            content=content,
            metadata_json=json.dumps(
                {
                    "model": model,
                    "temperature": payload.get("temperature"),
                    "memory_rounds": memory_rounds,
                    "rag_top_k": rag_top_k,
                    "context_router_enabled": enable_context_router,
                    "auto_route": auto_route,
                    "selected_route": selected_route,
                    "router": serialize_router_decision(router_decision),
                    "source": "frontend",
                },
                ensure_ascii=False,
            ),
        )
        room.updated_at = datetime.utcnow()
        session.add(user_message)
        session.flush()

        status = "ok"
        llm_error = ""
        route_gate_message = get_route_gate_message(selected_route, payload)

        if route_gate_message:
            assistant_content = route_gate_message
            assistant_metadata = {
                "model": model,
                "provider": "context_router",
                "memory_rounds": memory_rounds,
                "context_router_enabled": enable_context_router,
                "auto_route": auto_route,
                "selected_route": selected_route,
                "router": serialize_router_decision(router_decision),
                "source": "router_gate",
            }
        elif selected_route == "db_query":
            try:
                sql_agent_result = run_sql_agent(
                    api_key=current_app.config["OPENAI_API_KEY"],
                    question=content,
                    model=model,
                    temperature=temperature,
                )
                assistant_content = sql_agent_result["answer"]
                assistant_metadata = {
                    "model": model,
                    "provider": "sql_agent",
                    "memory_rounds": memory_rounds,
                    "context_router_enabled": enable_context_router,
                    "auto_route": auto_route,
                    "selected_route": selected_route,
                    "router": serialize_router_decision(router_decision),
                    "sql_agent": {
                        "route": sql_agent_result["route"],
                        "sql": sql_agent_result["sql"],
                        "raw_sql": sql_agent_result["raw_sql"],
                        "generator_reason": sql_agent_result["generator_reason"],
                        "generator_source": sql_agent_result["generator_source"],
                        "validator_warnings": sql_agent_result["validator_warnings"],
                        "columns": sql_agent_result["columns"],
                        "rows": sql_agent_result["rows"],
                        "row_count": sql_agent_result["row_count"],
                    },
                    "source": "sql_agent",
                }
            except SqlAgentError as exc:
                status = "sql_error"
                llm_error = str(exc)
                assistant_content = f"SQL Agent 查詢失敗：{llm_error}"
                assistant_metadata = {
                    "model": model,
                    "provider": "sql_agent",
                    "memory_rounds": memory_rounds,
                    "context_router_enabled": enable_context_router,
                    "auto_route": auto_route,
                    "selected_route": selected_route,
                    "router": serialize_router_decision(router_decision),
                    "error": llm_error,
                    "source": "sql_agent",
                }
        elif selected_route == "rag":
            try:
                rag_result = run_rag(
                    session=session,
                    api_key=current_app.config["OPENAI_API_KEY"],
                    query=content,
                    model=model,
                    temperature=temperature,
                    top_k=rag_top_k,
                )
                assistant_content = rag_result["answer"]
                assistant_metadata = {
                    "model": model,
                    "provider": "rag",
                    "memory_rounds": memory_rounds,
                    "rag_top_k": rag_top_k,
                    "context_router_enabled": enable_context_router,
                    "auto_route": auto_route,
                    "selected_route": selected_route,
                    "router": serialize_router_decision(router_decision),
                    "rag": {
                        "route": rag_result["route"],
                        "top_k": rag_result["top_k"],
                        "refs": rag_result["refs"],
                        "embedding_model": rag_result["embedding_model"],
                    },
                    "source": "rag",
                }
            except RagError as exc:
                status = "rag_error"
                llm_error = str(exc)
                assistant_content = f"RAG 查詢失敗：{llm_error}"
                assistant_metadata = {
                    "model": model,
                    "provider": "rag",
                    "memory_rounds": memory_rounds,
                    "rag_top_k": rag_top_k,
                    "context_router_enabled": enable_context_router,
                    "auto_route": auto_route,
                    "selected_route": selected_route,
                    "router": serialize_router_decision(router_decision),
                    "error": llm_error,
                    "source": "rag",
                }
        elif selected_route == "db_write":
            db_write_result = prepare_db_write(
                session=session,
                api_key=current_app.config["OPENAI_API_KEY"],
                message=content,
                model=model,
            )
            assistant_content = db_write_result["message"]
            assistant_metadata = {
                "model": model,
                "provider": "db_write_agent",
                "memory_rounds": memory_rounds,
                "context_router_enabled": enable_context_router,
                "auto_route": auto_route,
                "selected_route": selected_route,
                "router": serialize_router_decision(router_decision),
                "db_write": db_write_result,
                "source": "db_write_agent",
            }
        else:
            try:
                llm_result = generate_reply(
                    api_key=current_app.config["OPENAI_API_KEY"],
                    message=content,
                    model=model,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    history=history,
                    memory_rounds=memory_rounds,
                )
                assistant_content = llm_result["message"]
                assistant_metadata = {
                    "model": llm_result["model"],
                    "provider": llm_result["provider"],
                    "response_id": llm_result.get("response_id"),
                    "memory_rounds": llm_result.get("memory_rounds"),
                    "memory_message_count": llm_result.get("memory_message_count"),
                    "context_router_enabled": enable_context_router,
                    "auto_route": auto_route,
                    "selected_route": selected_route,
                    "router": serialize_router_decision(router_decision),
                    "source": "openai",
                }
            except MissingOpenAIKeyError as exc:
                status = "llm_error"
                llm_error = str(exc)
                assistant_content = f"LLM 尚未啟用：{llm_error}"
                assistant_metadata = {
                    "model": model,
                    "provider": "openai",
                    "memory_rounds": memory_rounds,
                    "context_router_enabled": enable_context_router,
                    "auto_route": auto_route,
                    "selected_route": selected_route,
                    "router": serialize_router_decision(router_decision),
                    "error": llm_error,
                    "source": "api",
                }
            except Exception as exc:
                status = "llm_error"
                llm_error = sanitize_error(exc, current_app.config["OPENAI_API_KEY"])
                assistant_content = f"LLM 呼叫失敗：{llm_error}"
                assistant_metadata = {
                    "model": model,
                    "provider": "openai",
                    "memory_rounds": memory_rounds,
                    "context_router_enabled": enable_context_router,
                    "auto_route": auto_route,
                    "selected_route": selected_route,
                    "router": serialize_router_decision(router_decision),
                    "error": llm_error,
                    "source": "api",
                }

        assistant_message = make_assistant_message(room.id, assistant_content, assistant_metadata)
        room.updated_at = datetime.utcnow()
        session.add(assistant_message)
        session.commit()

        return (
            jsonify(
                {
                    "status": status,
                    "room": serialize_room(room),
                    "messages": [serialize_message(user_message), serialize_message(assistant_message)],
                    "llm_error": llm_error,
                    "router": serialize_router_decision(router_decision),
                    "selected_route": selected_route,
                }
            ),
            201,
        )
    except SQLAlchemyError:
        session.rollback()
        return jsonify({"status": "error", "error": "資料庫操作失敗，請稍後再試。"}), 500
    finally:
        session.close()
