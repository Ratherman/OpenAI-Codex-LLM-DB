import json
from typing import Any

from sqlalchemy import func, select

from app.models import AuditLog


def compact_summary(value, max_length=360):
    text = str(value or "").strip()
    text = " ".join(text.split())
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 1]}..."


def normalize_usage(usage):
    usage = usage or {}
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")

    if total_tokens is None and (prompt_tokens is not None or completion_tokens is not None):
        total_tokens = int(prompt_tokens or 0) + int(completion_tokens or 0)

    return {
        "prompt_tokens": int(prompt_tokens) if prompt_tokens is not None else None,
        "completion_tokens": int(completion_tokens) if completion_tokens is not None else None,
        "total_tokens": int(total_tokens) if total_tokens is not None else None,
    }


def combine_usage(*usage_items):
    total_prompt = 0
    total_completion = 0
    total_total = 0
    has_any = False

    for usage in usage_items:
        normalized = normalize_usage(usage)
        if any(value is not None for value in normalized.values()):
            has_any = True
        total_prompt += normalized["prompt_tokens"] or 0
        total_completion += normalized["completion_tokens"] or 0
        total_total += normalized["total_tokens"] or 0

    if not has_any:
        return {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}

    return {
        "prompt_tokens": total_prompt or None,
        "completion_tokens": total_completion or None,
        "total_tokens": total_total or None,
    }


def create_audit_log(
    session,
    *,
    room_id=None,
    action_type,
    route,
    model=None,
    input_summary="",
    output_summary="",
    sql_text=None,
    db_table=None,
    db_record_id=None,
    usage=None,
    metadata=None,
    actor="agent",
    target_type=None,
    target_id=None,
):
    normalized_usage = normalize_usage(usage)
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

    audit_log = AuditLog(
        room_id=room_id,
        action_type=action_type,
        route=route,
        model=model,
        input_summary=compact_summary(input_summary),
        output_summary=compact_summary(output_summary),
        sql_text=sql_text,
        db_table=db_table,
        db_record_id=str(db_record_id) if db_record_id is not None else None,
        prompt_tokens=normalized_usage["prompt_tokens"],
        completion_tokens=normalized_usage["completion_tokens"],
        total_tokens=normalized_usage["total_tokens"],
        metadata_json=metadata_json,
        actor=actor,
        action=action_type,
        target_type=target_type or route,
        target_id=str(target_id) if target_id is not None else None,
        details=metadata_json,
    )
    session.add(audit_log)
    session.flush()
    return audit_log


def parse_audit_metadata(audit_log):
    try:
        return json.loads(audit_log.metadata_json or "{}")
    except json.JSONDecodeError:
        return {"raw": audit_log.metadata_json}


def serialize_audit_log(audit_log):
    return {
        "id": audit_log.id,
        "room_id": audit_log.room_id,
        "action_type": audit_log.action_type,
        "route": audit_log.route,
        "model": audit_log.model,
        "input_summary": audit_log.input_summary,
        "output_summary": audit_log.output_summary,
        "sql_text": audit_log.sql_text,
        "db_table": audit_log.db_table,
        "db_record_id": audit_log.db_record_id,
        "prompt_tokens": audit_log.prompt_tokens,
        "completion_tokens": audit_log.completion_tokens,
        "total_tokens": audit_log.total_tokens,
        "metadata": parse_audit_metadata(audit_log),
        "created_at": audit_log.created_at.isoformat(),
    }


def get_room_token_summary(session, room_id):
    row = session.execute(
        select(
            func.coalesce(func.sum(AuditLog.prompt_tokens), 0),
            func.coalesce(func.sum(AuditLog.completion_tokens), 0),
            func.coalesce(func.sum(AuditLog.total_tokens), 0),
            func.count(AuditLog.id),
        ).where(AuditLog.room_id == room_id)
    ).one()

    return {
        "prompt_tokens": int(row[0] or 0),
        "completion_tokens": int(row[1] or 0),
        "total_tokens": int(row[2] or 0),
        "audit_log_count": int(row[3] or 0),
    }


def list_room_audit_logs(session, room_id, limit=50):
    limit = max(1, min(100, int(limit or 50)))
    return session.execute(
        select(AuditLog)
        .where(AuditLog.room_id == room_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
    ).scalars().all()
