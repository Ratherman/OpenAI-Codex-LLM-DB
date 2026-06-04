import json
import re
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from openai import OpenAIError
from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import or_, select

from app.models import AuditLog, Employee, ExpenseReport, Invoice, Vendor
from app.services.llm_service import create_openai_client, sanitize_error

WriteToolName = Literal["create_expense_report", "create_invoice"]

DB_WRITE_EXTRACTOR_PROMPT = """
你是受控 DB Write 欄位抽取器。請只回傳 JSON object，不要加 Markdown。

只能抽取以下兩種白名單工具：
1. create_expense_report
2. create_invoice

不要產生 SQL。不要自行新增欄位。

create_expense_report 欄位：
- employee_name 或 employee_code
- vendor_name nullable
- expense_date，格式 YYYY-MM-DD
- category
- amount
- currency，預設 TWD
- description
- status，預設 pending

create_invoice 欄位：
- vendor_name nullable
- invoice_number
- invoice_date，格式 YYYY-MM-DD
- buyer_tax_id
- seller_tax_id
- total_amount
- raw_text nullable
- source_image_path nullable

JSON 格式：
{
  "tool": "create_expense_report | create_invoice",
  "fields": {
    "field_name": "value or null"
  },
  "reason": "用繁體中文簡短說明抽取依據"
}
""".strip()


class DbWriteExtraction(BaseModel):
    tool: WriteToolName
    fields: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    source: str = "openai"


class CreateExpenseReportInput(BaseModel):
    employee_name: str | None = None
    employee_code: str | None = None
    vendor_name: str | None = None
    expense_date: date
    category: str
    amount: Decimal = Field(gt=0)
    currency: str = "TWD"
    description: str
    status: str = "pending"

    @model_validator(mode="after")
    def require_employee_identifier(self):
        if not self.employee_name and not self.employee_code:
            raise ValueError("employee_name_or_employee_code_required")
        return self


class CreateInvoiceInput(BaseModel):
    vendor_name: str | None = None
    invoice_number: str
    invoice_date: date
    buyer_tax_id: str
    seller_tax_id: str
    total_amount: Decimal = Field(gt=0)
    raw_text: str | None = None
    source_image_path: str | None = None


class DbWriteError(RuntimeError):
    pass


def parse_json_object(raw_text):
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def compact_text(value):
    return str(value or "").strip()


def normalize_fields(fields):
    normalized = {}
    for key, value in (fields or {}).items():
        normalized[key] = compact_text(value) if isinstance(value, str) else value
    return normalized


def fallback_extract_db_write(message, reason):
    text = message.strip()
    lower_text = text.lower()

    if "發票" in text or "invoice" in lower_text:
        fields = {
            "vendor_name": None,
            "invoice_number": None,
            "invoice_date": None,
            "buyer_tax_id": None,
            "seller_tax_id": None,
            "total_amount": None,
            "raw_text": text,
            "source_image_path": None,
        }

        number_match = re.search(r"(?:號碼|發票號碼|invoice number)\s*([A-Z]{1,3}\d{6,10})", text, flags=re.IGNORECASE)
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        seller_match = re.search(r"賣方統編\s*(\d{8})", text)
        buyer_match = re.search(r"買方統編\s*(\d{8})", text)
        amount_match = re.search(r"(?:金額|總金額)\s*([0-9,]+(?:\.\d+)?)", text)
        vendor_match = re.search(r"廠商是([^，,。]+)", text)

        if number_match:
            fields["invoice_number"] = number_match.group(1)
        if date_match:
            fields["invoice_date"] = date_match.group(1)
        if seller_match:
            fields["seller_tax_id"] = seller_match.group(1)
        if buyer_match:
            fields["buyer_tax_id"] = buyer_match.group(1)
        if amount_match:
            fields["total_amount"] = amount_match.group(1).replace(",", "")
        if vendor_match:
            fields["vendor_name"] = vendor_match.group(1).strip()

        return DbWriteExtraction(
            tool="create_invoice",
            fields=fields,
            reason=reason,
            source="fallback",
        )

    fields = {
        "employee_name": None,
        "employee_code": None,
        "vendor_name": None,
        "expense_date": None,
        "category": None,
        "amount": None,
        "currency": "TWD",
        "description": None,
        "status": "pending",
    }

    code_match = re.search(r"\b(E\d{3})\b", text, flags=re.IGNORECASE)
    employee_match = re.search(r"幫\s+([A-Za-z][A-Za-z ]{1,50})\s+新增", text)
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    amount_match = re.search(r"([0-9,]+(?:\.\d+)?)\s*元", text)
    vendor_match = re.search(r"廠商是([^，,。]+)", text)
    category_match = re.search(r"類別([^，,。]+)", text)
    description_match = re.search(r"說明是([^，,。]+)", text)

    if code_match:
        fields["employee_code"] = code_match.group(1).upper()
    if employee_match:
        fields["employee_name"] = employee_match.group(1).strip()
    if date_match:
        fields["expense_date"] = date_match.group(1)
    if amount_match:
        fields["amount"] = amount_match.group(1).replace(",", "")
    if vendor_match:
        fields["vendor_name"] = vendor_match.group(1).strip()
    if category_match:
        fields["category"] = category_match.group(1).strip()
    elif "高鐵" in text:
        fields["category"] = "交通"
    if description_match:
        fields["description"] = description_match.group(1).strip()
    else:
        fields["description"] = text

    return DbWriteExtraction(
        tool="create_expense_report",
        fields=fields,
        reason=reason,
        source="fallback",
    )


def extract_db_write_request(api_key, message, model):
    if not api_key:
        return fallback_extract_db_write(message, "OPENAI_API_KEY 未設定，已使用規則 fallback 抽取欄位。")

    try:
        client = create_openai_client(api_key)
        response = client.responses.create(
            model=model,
            instructions=DB_WRITE_EXTRACTOR_PROMPT,
            input=[{"role": "user", "content": message}],
            temperature=0,
        )
        payload = parse_json_object(response.output_text)
        extraction = DbWriteExtraction.model_validate(payload)
        extraction.fields = normalize_fields(extraction.fields)
        extraction.source = "openai"
        return extraction
    except (json.JSONDecodeError, ValidationError) as exc:
        return fallback_extract_db_write(message, f"DB Write 抽取輸出不是合法 JSON，已使用 fallback：{exc}")
    except OpenAIError as exc:
        return fallback_extract_db_write(message, f"DB Write 抽取 API 呼叫失敗，已使用 fallback：{sanitize_error(exc, api_key)}")
    except Exception as exc:
        return fallback_extract_db_write(message, f"DB Write 抽取發生錯誤，已使用 fallback：{sanitize_error(exc, api_key)}")


def validation_missing_fields(error):
    missing = []
    for item in error.errors():
        location = item.get("loc") or []
        field = str(location[0]) if location else "欄位"
        if item.get("type") == "missing":
            missing.append(field)
        elif item.get("type") == "value_error" and "employee_name_or_employee_code_required" in str(item.get("msg")):
            missing.append("employee_name 或 employee_code")
        else:
            missing.append(field)
    return sorted(set(missing))


def find_employee(session, expense_input):
    query = select(Employee)
    if expense_input.employee_code:
        query = query.where(Employee.employee_code == expense_input.employee_code)
    else:
        query = query.where(Employee.name == expense_input.employee_name)
    return session.execute(query).scalar_one_or_none()


def find_vendor(session, vendor_name):
    if not vendor_name:
        return None

    return session.execute(
        select(Vendor).where(or_(Vendor.name == vendor_name, Vendor.name.like(f"%{vendor_name}%")))
    ).scalars().first()


def decimal_to_string(value):
    return str(value.quantize(Decimal("0.01")))


def prepare_expense_write(session, fields, extraction):
    warnings = []
    try:
        expense_input = CreateExpenseReportInput.model_validate(fields)
    except ValidationError as exc:
        missing = validation_missing_fields(exc)
        return {
            "status": "missing_fields",
            "tool": "create_expense_report",
            "fields": fields,
            "missing_fields": missing,
            "message": f"新增費用資料還缺少必要欄位：{', '.join(missing)}。請補充後再送出。",
            "reason": extraction.reason,
            "source": extraction.source,
        }

    employee = find_employee(session, expense_input)
    if not employee:
        identifier = expense_input.employee_code or expense_input.employee_name
        return {
            "status": "missing_fields",
            "tool": "create_expense_report",
            "fields": expense_input.model_dump(mode="json"),
            "missing_fields": ["employee_name 或 employee_code"],
            "message": f"找不到員工「{identifier}」。請提供正確的 employee_code 或員工姓名。",
            "reason": extraction.reason,
            "source": extraction.source,
        }

    vendor = find_vendor(session, expense_input.vendor_name)
    if expense_input.vendor_name and not vendor:
        warnings.append(f"找不到廠商「{expense_input.vendor_name}」，將以未關聯廠商寫入。")

    fields_json = expense_input.model_dump(mode="json")
    fields_json["amount"] = decimal_to_string(expense_input.amount)

    return {
        "status": "pending_confirmation",
        "tool": "create_expense_report",
        "fields": fields_json,
        "resolved": {
            "employee_id": employee.id,
            "employee_name": employee.name,
            "employee_code": employee.employee_code,
            "vendor_id": vendor.id if vendor else None,
            "vendor_name": vendor.name if vendor else expense_input.vendor_name,
        },
        "warnings": warnings,
        "message": "已整理出一筆待確認寫入的費用資料，請確認後再寫入資料庫。",
        "reason": extraction.reason,
        "source": extraction.source,
    }


def prepare_invoice_write(session, fields, extraction):
    warnings = []
    try:
        invoice_input = CreateInvoiceInput.model_validate(fields)
    except ValidationError as exc:
        missing = validation_missing_fields(exc)
        return {
            "status": "missing_fields",
            "tool": "create_invoice",
            "fields": fields,
            "missing_fields": missing,
            "message": f"新增發票資料還缺少必要欄位：{', '.join(missing)}。請補充後再送出。",
            "reason": extraction.reason,
            "source": extraction.source,
        }

    vendor = find_vendor(session, invoice_input.vendor_name)
    if invoice_input.vendor_name and not vendor:
        warnings.append(f"找不到廠商「{invoice_input.vendor_name}」，將以未關聯廠商寫入。")

    fields_json = invoice_input.model_dump(mode="json")
    fields_json["total_amount"] = decimal_to_string(invoice_input.total_amount)

    return {
        "status": "pending_confirmation",
        "tool": "create_invoice",
        "fields": fields_json,
        "resolved": {
            "vendor_id": vendor.id if vendor else None,
            "vendor_name": vendor.name if vendor else invoice_input.vendor_name,
        },
        "warnings": warnings,
        "message": "已整理出一筆待確認寫入的發票資料，請確認後再寫入資料庫。",
        "reason": extraction.reason,
        "source": extraction.source,
    }


def prepare_db_write(session, api_key, message, model):
    extraction = extract_db_write_request(api_key=api_key, message=message, model=model)
    fields = normalize_fields(extraction.fields)

    if extraction.tool == "create_expense_report":
        return prepare_expense_write(session, fields, extraction)

    if extraction.tool == "create_invoice":
        return prepare_invoice_write(session, fields, extraction)

    return {
        "status": "missing_fields",
        "tool": extraction.tool,
        "fields": fields,
        "missing_fields": ["tool"],
        "message": "目前只支援 create_expense_report 與 create_invoice。",
        "reason": extraction.reason,
        "source": extraction.source,
    }


def confirm_expense_write(session, pending_write):
    expense_input = CreateExpenseReportInput.model_validate(pending_write["fields"])
    employee = find_employee(session, expense_input)
    if not employee:
        raise DbWriteError("確認寫入失敗：找不到指定員工。")

    vendor = find_vendor(session, expense_input.vendor_name)
    expense = ExpenseReport(
        employee_id=employee.id,
        vendor_id=vendor.id if vendor else None,
        expense_date=expense_input.expense_date,
        category=expense_input.category,
        amount=expense_input.amount,
        currency=expense_input.currency or "TWD",
        status=expense_input.status or "pending",
        description=expense_input.description,
    )
    session.add(expense)
    session.flush()
    return expense


def confirm_invoice_write(session, pending_write):
    invoice_input = CreateInvoiceInput.model_validate(pending_write["fields"])
    vendor = find_vendor(session, invoice_input.vendor_name)
    invoice = Invoice(
        vendor_id=vendor.id if vendor else None,
        invoice_number=invoice_input.invoice_number,
        invoice_date=invoice_input.invoice_date,
        buyer_tax_id=invoice_input.buyer_tax_id,
        seller_tax_id=invoice_input.seller_tax_id,
        total_amount=invoice_input.total_amount,
        raw_text=invoice_input.raw_text or "",
        source_image_path=invoice_input.source_image_path,
    )
    session.add(invoice)
    session.flush()
    return invoice


def confirm_db_write(session, pending_write, actor="user"):
    if pending_write.get("status") != "pending_confirmation":
        raise DbWriteError("這筆資料不是待確認寫入狀態。")

    tool = pending_write.get("tool")
    if tool == "create_expense_report":
        record = confirm_expense_write(session, pending_write)
        target_type = "expense_report"
        action = "create_expense_report"
        success_message = f"寫入成功：已新增費用資料 ID {record.id}。"
    elif tool == "create_invoice":
        record = confirm_invoice_write(session, pending_write)
        target_type = "invoice"
        action = "create_invoice"
        success_message = f"寫入成功：已新增發票資料 ID {record.id}。"
    else:
        raise DbWriteError("不支援的寫入工具。")

    audit_log = AuditLog(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=str(record.id),
        details=json.dumps(
            {
                "tool": tool,
                "fields": pending_write.get("fields"),
                "resolved": pending_write.get("resolved"),
            },
            ensure_ascii=False,
        ),
    )
    session.add(audit_log)
    session.flush()

    return {
        "status": "confirmed",
        "tool": tool,
        "record_id": record.id,
        "target_type": target_type,
        "audit_log_id": audit_log.id,
        "message": success_message,
    }
