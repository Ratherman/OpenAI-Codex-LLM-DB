import json
from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_session
from app.models import ChatMessage, ChatRoom

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


@chat_rooms_bp.post("/api/chat/rooms/<int:room_id>/messages")
def create_chat_room_message(room_id):
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

        user_message = ChatMessage(
            room_id=room.id,
            role="user",
            content=content,
            metadata_json=json.dumps(
                {
                    "model": model,
                    "temperature": payload.get("temperature"),
                    "source": "frontend",
                },
                ensure_ascii=False,
            ),
        )
        assistant_message = ChatMessage(
            room_id=room.id,
            role="assistant",
            content=f"後端已收到你的訊息：{content}。下一階段會由 LLM 回覆。",
            metadata_json=json.dumps(
                {
                    "model": model,
                    "provider": "backend_mock",
                    "source": "api",
                },
                ensure_ascii=False,
            ),
        )
        room.updated_at = datetime.utcnow()
        session.add_all([user_message, assistant_message])
        session.commit()

        return (
            jsonify(
                {
                    "status": "ok",
                    "room": serialize_room(room),
                    "messages": [serialize_message(user_message), serialize_message(assistant_message)],
                }
            ),
            201,
        )
    except SQLAlchemyError as exc:
        session.rollback()
        return jsonify({"status": "error", "error": str(exc)}), 500
    finally:
        session.close()
