import json
import re
from typing import Literal

from openai import OpenAIError
from pydantic import BaseModel, Field, ValidationError

from app.services.llm_service import create_openai_client, extract_token_usage, sanitize_error

RouteName = Literal["general_chat", "db_query", "db_write", "rag", "image_skill"]

ROUTE_NAMES = ("general_chat", "db_query", "db_write", "rag", "image_skill")

ROUTE_CAPABILITIES = {
    "general_chat": "general_chat",
    "db_query": "db_query",
    "db_write": "db_write",
    "rag": "rag",
    "image_skill": "image_skill",
}

ROUTER_SYSTEM_PROMPT = """
你是 DB Agent Chat 的 Context Router。請只回傳一個 JSON object，不要加 Markdown。

可用 route：
1. general_chat：一般聊天、閒聊、寫作、摘要、翻譯。
2. db_query：查詢 MySQL 內的營運資料，例如員工、部門、費用紀錄、發票資料、廠商資料。
3. db_write：新增或修改資料庫資料，例如新增費用、寫入發票、更新員工資料。
4. rag：查公司 MIS / 行政 SOP / 制度流程 / 常見問題，例如忘記密碼、VPN 無法連線、Gmail 無法寄信、筆電黑畫面、印表機無法列印、發票報銷流程、出差費用核銷規則。
5. image_skill：圖片辨識，例如發票、收據、文件截圖、請辨識這張圖片。

判斷提示：
- 問「有哪些員工、費用總額、哪個廠商發票最高」這類要查資料庫內容的問題走 db_query。
- 問「怎麼報銷、流程、規則、SOP、怎麼辦」這類政策/操作說明走 rag。
- 問「新增、建立、寫入、記一筆」這類要新增資料走 db_write。

JSON 欄位：
{
  "route": "general_chat | db_query | db_write | rag | image_skill",
  "confidence": 0.0 到 1.0,
  "reason": "用繁體中文簡短說明判斷原因",
  "required_capability": "general_chat | db_query | db_write | rag | image_skill",
  "suggested_followup_question": null 或一個繁體中文追問
}
""".strip()


class RouterDecision(BaseModel):
    route: RouteName
    confidence: float = Field(ge=0, le=1)
    reason: str
    required_capability: str
    suggested_followup_question: str | None = None
    usage: dict | None = None


def normalize_route(route):
    normalized = str(route or "").strip().lower()
    return normalized if normalized in ROUTE_NAMES else "general_chat"


def normalize_router_payload(payload):
    route = normalize_route(payload.get("route"))
    confidence = payload.get("confidence", 0.5)

    try:
        confidence = max(0, min(1, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.5

    return {
        "route": route,
        "confidence": confidence,
        "reason": str(payload.get("reason") or "Router fallback 判斷。"),
        "required_capability": str(payload.get("required_capability") or ROUTE_CAPABILITIES[route]),
        "suggested_followup_question": payload.get("suggested_followup_question"),
    }


def parse_router_json(raw_text):
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
        if not match:
            raise
        payload = json.loads(match.group(0))

    return RouterDecision.model_validate(normalize_router_payload(payload))


def keyword_fallback(message, reason):
    text = message.lower()

    rag_keywords = [
        "sop",
        "mis",
        "vpn",
        "密碼",
        "忘記密碼",
        "連不上",
        "怎麼辦",
        "流程",
        "規則",
        "報銷",
        "核銷",
        "無法寄信",
        "gmail",
        "黑畫面",
        "印表機",
        "卡紙",
        "門禁",
        "mfa",
        "釣魚",
    ]
    image_keywords = ["圖片", "照片", "截圖", "辨識", "收據", "這張", "這個檔案", "拍照"]
    write_keywords = ["新增", "建立", "寫入", "修改", "更新", "刪除", "新增一筆", "記一筆"]
    db_keywords = ["員工", "部門", "費用", "發票", "廠商", "資訊部", "財務", "查詢", "有哪些", "清單", "總額"]

    if any(keyword in text for keyword in image_keywords):
        route = "image_skill"
        confidence = 0.82
    elif any(keyword in text for keyword in write_keywords):
        route = "db_write"
        confidence = 0.82
    elif any(keyword in text for keyword in rag_keywords):
        route = "rag"
        confidence = 0.82
    elif any(keyword in text for keyword in db_keywords):
        route = "db_query"
        confidence = 0.78
    else:
        route = "general_chat"
        confidence = 0.7

    return RouterDecision(
        route=route,
        confidence=confidence,
        reason=reason,
        required_capability=ROUTE_CAPABILITIES[route],
        suggested_followup_question=None,
    )


def apply_keyword_guardrail(message, decision):
    keyword_decision = keyword_fallback(message, "關鍵字 guardrail 判斷。")

    if keyword_decision.route == "general_chat" or keyword_decision.route == decision.route:
        return decision

    if decision.confidence >= 0.95:
        return decision

    return RouterDecision(
        route=keyword_decision.route,
        confidence=max(decision.confidence, keyword_decision.confidence),
        reason=f"{decision.reason}；關鍵字 guardrail 修正為 {keyword_decision.route}。",
        required_capability=ROUTE_CAPABILITIES[keyword_decision.route],
        suggested_followup_question=decision.suggested_followup_question,
    )


def route_message(api_key, message, model):
    if not api_key:
        return keyword_fallback(message, "OPENAI_API_KEY 未設定，已使用關鍵字 fallback。")

    try:
        client = create_openai_client(api_key)
        response = client.responses.create(
            model=model,
            instructions=ROUTER_SYSTEM_PROMPT,
            input=[{"role": "user", "content": message}],
            temperature=0,
        )
        decision = apply_keyword_guardrail(message, parse_router_json(response.output_text))
        decision.usage = extract_token_usage(response)
        return decision
    except (json.JSONDecodeError, ValidationError) as exc:
        return keyword_fallback(message, f"Router 輸出不是合法 JSON，已使用 fallback：{exc}")
    except OpenAIError as exc:
        return keyword_fallback(message, f"Router API 呼叫失敗，已使用 fallback：{sanitize_error(exc, api_key)}")
    except Exception as exc:
        return keyword_fallback(message, f"Router 發生錯誤，已使用 fallback：{sanitize_error(exc, api_key)}")
