import json
import re
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_session
from app.models import AuditLog, ChatMessage, ChatRoom
from app.services.db_write_service import (
    DbWriteError,
    DbWriteExtraction,
    confirm_db_write,
    prepare_db_write,
    prepare_invoice_write,
)
from app.services.invoice_extraction_service import (
    InvoiceExtractionError,
    build_invoice_fields_from_extraction,
    extract_invoice_from_image,
)
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


def normalize_image_attachments(raw_attachments):
    if not raw_attachments:
        return []
    if not isinstance(raw_attachments, list):
        return []

    attachments = []
    for attachment in raw_attachments:
        if not isinstance(attachment, dict):
            continue
        content_type = str(attachment.get("content_type") or "")
        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            continue
        attachments.append(
            {
                "filename": str(attachment.get("filename") or ""),
                "original_filename": str(attachment.get("original_filename") or ""),
                "content_type": content_type,
                "size": int(attachment.get("size") or 0),
                "path": str(attachment.get("path") or ""),
                "url": str(attachment.get("url") or ""),
            }
        )
    return attachments


def with_image_router_context(content, attachments):
    if not attachments:
        return content
    return (
        f"{content}\n\n"
        "[系統補充：使用者已上傳圖片。若任務需要辨識發票、收據、文件截圖或圖片內容，請選 image_skill。]"
    )


def find_latest_open_invoice_write(session, room_id, limit=30):
    messages = session.execute(
        select(ChatMessage)
        .where(ChatMessage.room_id == room_id, ChatMessage.role == "assistant")
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(limit)
    ).scalars()

    for message in messages:
        metadata = parse_metadata(message.metadata_json)
        db_write = metadata.get("db_write")
        if not isinstance(db_write, dict):
            continue
        if db_write.get("tool") != "create_invoice":
            continue
        if db_write.get("status") not in {"missing_fields", "pending_confirmation"}:
            continue
        return {
            "message": message,
            "metadata": metadata,
            "db_write": db_write,
            "image_skill": metadata.get("image_skill") or {},
        }
    return None


def extract_invoice_followup_fields(content, pending_write):
    text = str(content or "").strip()
    lower_text = text.lower()
    missing_fields = set(pending_write.get("missing_fields") or [])
    fields = {}

    tax_ids = re.findall(r"\b\d{8}\b", text)
    if tax_ids:
        if re.search(r"buyer\s*tax\s*id|buyer_tax_id|買方|買受人", lower_text, flags=re.IGNORECASE):
            fields["buyer_tax_id"] = tax_ids[0]
        elif re.search(r"seller\s*tax\s*id|seller_tax_id|賣方|營業人", lower_text, flags=re.IGNORECASE):
            fields["seller_tax_id"] = tax_ids[0]
        elif "buyer_tax_id" in missing_fields and "seller_tax_id" not in missing_fields:
            fields["buyer_tax_id"] = tax_ids[0]
        elif "seller_tax_id" in missing_fields and "buyer_tax_id" not in missing_fields:
            fields["seller_tax_id"] = tax_ids[0]

    invoice_number_match = re.search(r"\b[A-Z]{1,3}\d{6,10}\b", text, flags=re.IGNORECASE)
    if invoice_number_match and (
        "invoice_number" in missing_fields or re.search(r"invoice|發票號碼|號碼", lower_text, flags=re.IGNORECASE)
    ):
        fields["invoice_number"] = invoice_number_match.group(0).upper()

    date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
    if date_match and ("invoice_date" in missing_fields or "日期" in text or "date" in lower_text):
        fields["invoice_date"] = date_match.group(0)

    amount_match = re.search(r"(?:total_amount|總金額|金額|amount)\D{0,12}([0-9,]+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    if amount_match:
        fields["total_amount"] = amount_match.group(1).replace(",", "")

    vendor_match = re.search(r"(?:vendor_name|vendor|廠商|賣方|店家)\s*(?:是|:|：)?\s*([^，,。\\n]{2,80})", text, flags=re.IGNORECASE)
    if vendor_match and "vendor_name" in missing_fields:
        fields["vendor_name"] = vendor_match.group(1).strip()

    return fields


def is_invoice_followup_content(content):
    text = str(content or "").lower()
    return bool(
        re.search(
            r"buyer\s*tax\s*id|seller\s*tax\s*id|buyer_tax_id|seller_tax_id|tax id|統編|買方|賣方|"
            r"發票|invoice|剛剛|剛才|補充|彙整|整理|列點|寫入|確認",
            text,
            flags=re.IGNORECASE,
        )
    )


def build_pending_invoice_router_decision():
    return RouterDecision(
        route="image_skill",
        confidence=1,
        reason="接續上一筆發票圖片辨識結果，使用者正在補充或整理待確認的發票欄位。",
        required_capability=ROUTE_CAPABILITIES["image_skill"],
        suggested_followup_question=None,
    )


def summarize_invoice_fields(fields, missing_fields=None):
    lines = ["目前整理到的發票資訊如下："]
    labels = [
        ("invoice_number", "發票號碼"),
        ("invoice_date", "發票日期"),
        ("buyer_tax_id", "買方統編"),
        ("seller_tax_id", "賣方統編"),
        ("vendor_name", "廠商名稱"),
        ("total_amount", "總金額"),
        ("source_image_path", "圖片路徑"),
    ]
    for key, label in labels:
        value = fields.get(key)
        lines.append(f"- {label}：{value if value not in (None, '') else '尚未取得'}")

    if missing_fields:
        lines.append("")
        lines.append(f"仍缺少欄位：{', '.join(missing_fields)}。")
    else:
        lines.append("")
        lines.append("欄位已足夠，可以確認寫入資料庫。")
    return "\n".join(lines)


def build_pending_invoice_followup_response(session, room_id, content, pending_invoice, model, router_decision):
    pending_write = pending_invoice["db_write"]
    image_skill = pending_invoice["image_skill"]
    current_fields = dict(pending_write.get("fields") or {})
    updates = extract_invoice_followup_fields(content, pending_write)
    merged_fields = {**current_fields, **updates}

    extraction = DbWriteExtraction(
        tool="create_invoice",
        fields=merged_fields,
        reason="接續上一張發票圖片辨識結果，合併使用者補充欄位。",
        source="image_skill_followup",
    )
    db_write_result = prepare_invoice_write(session=session, fields=merged_fields, extraction=extraction)
    db_write_result["origin"] = "image_skill_followup"

    image = pending_write.get("image") or image_skill.get("image")
    if image:
        db_write_result["image"] = image

    image_extraction = dict(image_skill.get("extraction") or {})
    for key, value in merged_fields.items():
        if key in image_extraction:
            image_extraction[key] = value

    missing_fields = db_write_result.get("missing_fields") or []
    if updates and db_write_result["status"] == "pending_confirmation":
        assistant_content = "已補上你提供的發票資訊，請確認下方欄位後再寫入資料庫。"
    elif updates:
        assistant_content = summarize_invoice_fields(merged_fields, missing_fields)
    else:
        assistant_content = summarize_invoice_fields(merged_fields, pending_write.get("missing_fields"))

    if db_write_result["status"] == "missing_fields":
        db_write_result["message"] = assistant_content

    audit_log = AuditLog(
        actor="frontend_user",
        action="image_invoice_followup",
        target_type="chat_room",
        target_id=str(room_id),
        details=json.dumps(
            {
                "source_message_id": pending_invoice["message"].id,
                "updates": updates,
                "merged_fields": merged_fields,
                "db_write_status": db_write_result.get("status"),
            },
            ensure_ascii=False,
        ),
    )
    session.add(audit_log)
    session.flush()

    return assistant_content, {
        "model": model,
        "provider": "image_skill",
        "context_router_enabled": True,
        "auto_route": True,
        "selected_route": "image_skill",
        "router": serialize_router_decision(router_decision),
        "image_skill": {
            "route": "Image Skill",
            "status": db_write_result["status"],
            "image": image,
            "extraction": image_extraction,
            "followup_updates": updates,
            "source_message_id": pending_invoice["message"].id,
            "audit_log_id": audit_log.id,
        },
        "db_write": db_write_result,
        "source": "image_skill_followup",
    }


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


def get_route_gate_message(route, payload):
    if route == "general_chat":
        return None

    if route == "db_query" and not parse_bool(payload, "enableDbQuery", False):
        return "DB Query 尚未啟用，請先在右側開啟。"

    if route == "rag" and not parse_bool(payload, "enableRag", False):
        return "RAG 尚未啟用，請先在右側開啟。"

    if route == "image_skill" and not parse_bool(payload, "enableImageSkill", False):
        return "Image Skill 尚未啟用，請先在右側開啟。"

    if route in {"db_query", "db_write", "rag", "image_skill"}:
        return None

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
    attachments = normalize_image_attachments(payload.get("attachments"))

    if not content and attachments:
        content = "請辨識這張圖片。"

    if not content:
        return jsonify({"status": "error", "error": "message is required"}), 400

    session = get_session()
    try:
        room, error_response = get_room_or_404(session, room_id)
        if error_response:
            return error_response

        decision = route_message(
            api_key=current_app.config["OPENAI_API_KEY"],
            message=with_image_router_context(content, attachments),
            model=model,
        )
        pending_invoice = find_latest_open_invoice_write(session, room.id)
        if pending_invoice and not attachments and is_invoice_followup_content(content):
            decision = build_pending_invoice_router_decision()
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
    image_attachments = normalize_image_attachments(payload.get("attachments"))

    if not content and image_attachments:
        content = "請辨識這張圖片。"

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
                content=with_image_router_context(content, image_attachments),
                model=model,
                api_key=current_app.config["OPENAI_API_KEY"],
            )
            selected_route = router_decision.route

        pending_invoice = find_latest_open_invoice_write(session, room.id)
        should_continue_pending_invoice = bool(
            pending_invoice and not image_attachments and is_invoice_followup_content(content)
        )
        if should_continue_pending_invoice:
            selected_route = "image_skill"
            router_decision = build_pending_invoice_router_decision()

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
                    "attachments": image_attachments,
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
        elif selected_route == "image_skill":
            if should_continue_pending_invoice:
                assistant_content, assistant_metadata = build_pending_invoice_followup_response(
                    session=session,
                    room_id=room.id,
                    content=content,
                    pending_invoice=pending_invoice,
                    model=model,
                    router_decision=router_decision,
                )
            elif not image_attachments:
                assistant_content = "請先上傳圖片，再使用 Image Skill 進行發票或收據辨識。"
                assistant_metadata = {
                    "model": model,
                    "provider": "image_skill",
                    "memory_rounds": memory_rounds,
                    "context_router_enabled": enable_context_router,
                    "auto_route": auto_route,
                    "selected_route": selected_route,
                    "router": serialize_router_decision(router_decision),
                    "image_skill": {
                        "route": "Image Skill",
                        "status": "missing_image",
                        "message": assistant_content,
                    },
                    "source": "image_skill",
                }
            else:
                image = image_attachments[0]
                try:
                    extraction_result = extract_invoice_from_image(
                        api_key=current_app.config["OPENAI_API_KEY"],
                        image=image,
                        message=content,
                        model=model,
                        upload_folder=current_app.config["UPLOAD_FOLDER"],
                    )
                    extraction = extraction_result["extraction"]
                    invoice_fields = build_invoice_fields_from_extraction(extraction, image)
                    db_write_extraction = DbWriteExtraction(
                        tool="create_invoice",
                        fields=invoice_fields,
                        reason="由 Image Skill 辨識發票圖片後產生待確認寫入資料。",
                        source="image_skill",
                    )
                    db_write_result = prepare_invoice_write(
                        session=session,
                        fields=invoice_fields,
                        extraction=db_write_extraction,
                    )
                    db_write_result["origin"] = "image_skill"
                    db_write_result["image"] = image

                    if db_write_result["status"] == "pending_confirmation":
                        assistant_content = "辨識完成，請確認下方發票欄位後再寫入資料庫。"
                    else:
                        assistant_content = "辨識完成，但缺少必要欄位，請補充後再寫入資料庫。"
                        db_write_result["message"] = assistant_content

                    audit_log = AuditLog(
                        actor="frontend_user",
                        action="image_invoice_extraction",
                        target_type="upload",
                        target_id=image.get("filename"),
                        details=json.dumps(
                            {
                                "room_id": room.id,
                                "image": image,
                                "extraction": extraction,
                                "db_write_status": db_write_result.get("status"),
                            },
                            ensure_ascii=False,
                        ),
                    )
                    session.add(audit_log)
                    session.flush()

                    assistant_metadata = {
                        "model": extraction_result["model"],
                        "provider": "image_skill",
                        "response_id": extraction_result.get("response_id"),
                        "memory_rounds": memory_rounds,
                        "context_router_enabled": enable_context_router,
                        "auto_route": auto_route,
                        "selected_route": selected_route,
                        "router": serialize_router_decision(router_decision),
                        "image_skill": {
                            "route": "Image Skill",
                            "status": "pending_confirmation",
                            "image": image,
                            "extraction": extraction,
                            "audit_log_id": audit_log.id,
                        },
                        "db_write": db_write_result,
                        "source": "image_skill",
                    }
                except InvoiceExtractionError as exc:
                    status = "image_error"
                    llm_error = str(exc)
                    assistant_content = f"圖片辨識失敗：{llm_error}"
                    audit_log = AuditLog(
                        actor="frontend_user",
                        action="image_invoice_extraction_failed",
                        target_type="upload",
                        target_id=image.get("filename"),
                        details=json.dumps(
                            {
                                "room_id": room.id,
                                "image": image,
                                "error": llm_error,
                            },
                            ensure_ascii=False,
                        ),
                    )
                    session.add(audit_log)
                    session.flush()
                    assistant_metadata = {
                        "model": model,
                        "provider": "image_skill",
                        "memory_rounds": memory_rounds,
                        "context_router_enabled": enable_context_router,
                        "auto_route": auto_route,
                        "selected_route": selected_route,
                        "router": serialize_router_decision(router_decision),
                        "image_skill": {
                            "route": "Image Skill",
                            "status": "error",
                            "image": image,
                            "error": llm_error,
                            "audit_log_id": audit_log.id,
                        },
                        "error": llm_error,
                        "source": "image_skill",
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
