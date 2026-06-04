import base64
import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from openai import OpenAIError
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.services.llm_service import create_openai_client, extract_token_usage, sanitize_error

SKILL_PATH = Path(__file__).resolve().parents[1] / "skills" / "invoice_extraction" / "SKILL.md"
DEFAULT_VISION_MODEL = "gpt-4o"


class InvoiceExtractionError(RuntimeError):
    pass


class InvoiceItem(BaseModel):
    description: str | None = None
    quantity: Decimal | None = Field(default=None, ge=0)
    unit_price: Decimal | None = Field(default=None, ge=0)
    amount: Decimal | None = Field(default=None, ge=0)

    @field_validator("description", mode="before")
    @classmethod
    def blank_description_to_none(cls, value):
        if value == "":
            return None
        return value

    @field_validator("quantity", "unit_price", "amount", mode="before")
    @classmethod
    def clean_decimal(cls, value):
        if value in ("", None):
            return None
        if isinstance(value, str):
            return value.replace(",", "").strip()
        return value


class InvoiceExtractionResult(BaseModel):
    invoice_number: str | None = None
    invoice_date: date | None = None
    buyer_tax_id: str | None = None
    seller_tax_id: str | None = None
    vendor_name: str | None = None
    items: list[InvoiceItem] = Field(default_factory=list)
    total_amount: Decimal | None = Field(default=None, ge=0)
    raw_text: str | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    notes: list[str] = Field(default_factory=list)

    @field_validator(
        "invoice_number",
        "buyer_tax_id",
        "seller_tax_id",
        "vendor_name",
        "raw_text",
        mode="before",
    )
    @classmethod
    def blank_string_to_none(cls, value):
        if value == "":
            return None
        return value

    @field_validator("total_amount", mode="before")
    @classmethod
    def clean_total_amount(cls, value):
        if value in ("", None):
            return None
        if isinstance(value, str):
            return value.replace(",", "").strip()
        return value

    @field_validator("invoice_date", mode="before")
    @classmethod
    def clean_invoice_date(cls, value):
        if value in ("", None):
            return None
        return value


def parse_json_object(raw_text):
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def decimal_to_json(value):
    if value is None:
        return None
    return str(value.normalize()) if value == value.to_integral() else str(value)


def load_skill_instructions():
    return SKILL_PATH.read_text(encoding="utf-8")


def resolve_uploaded_image_path(image, upload_folder):
    filename = str(image.get("filename") or "").strip()
    if filename:
        candidate = Path(upload_folder) / filename
    else:
        raw_path = str(image.get("path") or "").strip().replace("\\", "/")
        if raw_path.startswith("uploads/"):
            candidate = Path(upload_folder) / Path(raw_path).name
        else:
            raise InvoiceExtractionError("找不到圖片檔案資訊，請重新上傳圖片。")

    upload_root = Path(upload_folder).resolve()
    resolved = candidate.resolve()
    if upload_root not in resolved.parents and resolved != upload_root:
        raise InvoiceExtractionError("圖片路徑不合法，請重新上傳圖片。")
    if not resolved.exists():
        raise InvoiceExtractionError("圖片檔案不存在，請重新上傳圖片。")
    return resolved


def encode_image_as_data_url(image_path, content_type):
    with image_path.open("rb") as file:
        image_base64 = base64.b64encode(file.read()).decode("utf-8")
    return f"data:{content_type};base64,{image_base64}"


def normalize_vision_model(model):
    candidate = str(model or "").strip()
    return candidate or DEFAULT_VISION_MODEL


def extract_invoice_from_image(api_key, image, message, model, upload_folder):
    if not api_key:
        raise InvoiceExtractionError("OPENAI_API_KEY 未設定，無法進行圖片辨識。請先設定 .env 並重啟後端。")

    image_path = resolve_uploaded_image_path(image, upload_folder)
    content_type = image.get("content_type") or "image/jpeg"
    data_url = encode_image_as_data_url(image_path, content_type)
    instructions = load_skill_instructions()

    prompt = "\n".join(
        [
            "請辨識這張發票或收據圖片，並依照 skill 的 JSON 格式輸出。",
            "使用者補充文字：",
            message or "（沒有補充文字）",
        ]
    )

    try:
        client = create_openai_client(api_key)
        response = client.responses.create(
            model=normalize_vision_model(model),
            instructions=instructions,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": data_url, "detail": "high"},
                    ],
                }
            ],
            temperature=0,
        )
        payload = parse_json_object(response.output_text)
        extraction = InvoiceExtractionResult.model_validate(payload)
        return {
            "status": "ok",
            "model": normalize_vision_model(model),
            "extraction": extraction.model_dump(mode="json"),
            "response_id": getattr(response, "id", None),
            "usage": extract_token_usage(response),
        }
    except (json.JSONDecodeError, ValidationError) as exc:
        raise InvoiceExtractionError(f"LLM 回傳的發票辨識結果格式不正確：{exc}") from exc
    except OpenAIError as exc:
        raise InvoiceExtractionError(f"OpenAI 圖片辨識失敗：{sanitize_error(exc, api_key)}") from exc
    except Exception as exc:
        if isinstance(exc, InvoiceExtractionError):
            raise
        raise InvoiceExtractionError(f"圖片辨識失敗：{sanitize_error(exc, api_key)}") from exc


def build_invoice_fields_from_extraction(extraction: dict[str, Any], image: dict[str, Any]):
    return {
        "vendor_name": extraction.get("vendor_name"),
        "invoice_number": extraction.get("invoice_number"),
        "invoice_date": extraction.get("invoice_date"),
        "buyer_tax_id": extraction.get("buyer_tax_id"),
        "seller_tax_id": extraction.get("seller_tax_id"),
        "total_amount": extraction.get("total_amount"),
        "raw_text": extraction.get("raw_text"),
        "source_image_path": image.get("path"),
    }
