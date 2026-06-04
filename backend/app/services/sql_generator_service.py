import json
import re

from openai import OpenAIError
from pydantic import BaseModel, ValidationError

from app.services.llm_service import create_openai_client, sanitize_error

SQL_GENERATOR_PROMPT = """
你是安全的 MySQL SQL Generator。請只回傳 JSON object，不要加 Markdown。

任務：把使用者問題轉成單一 MySQL SELECT 查詢。

硬性規則：
- 只能產生 SELECT。
- 不可產生 INSERT、UPDATE、DELETE、DROP、ALTER、TRUNCATE、CREATE。
- 不可產生多語句。
- 必須加 LIMIT，最多 LIMIT 50。
- 只能使用提供的 business schema。
- 不要查 chat_rooms、chat_messages、audit_logs 或任何系統表。
- 如果使用者使用中文部門名稱，請參考 schema 裡的 Business aliases。

JSON 格式：
{
  "sql": "SELECT ... LIMIT 50",
  "reason": "用繁體中文簡短說明 SQL 如何回答問題"
}
""".strip()


class GeneratedSql(BaseModel):
    sql: str
    reason: str
    source: str = "openai"


def parse_generated_sql(raw_text):
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
        if not match:
            raise
        payload = json.loads(match.group(0))

    return GeneratedSql.model_validate(payload)


def fallback_sql_for_question(question, reason):
    text = question.lower()

    if any(keyword in text for keyword in ["資訊部", "工程部", "研發部", "engineering"]) and any(
        keyword in text for keyword in ["員工", "employee", "email", "職稱"]
    ):
        sql = """
        SELECT e.name, e.title, e.email
        FROM employees e
        JOIN departments d ON e.department_id = d.id
        WHERE d.name = 'Engineering'
        ORDER BY e.name
        LIMIT 50
        """
    elif "各部門" in text and any(keyword in text for keyword in ["費用總額", "費用", "金額"]):
        sql = """
        SELECT d.name AS department_name, COALESCE(SUM(er.amount), 0) AS total_expense
        FROM departments d
        LEFT JOIN employees e ON e.department_id = d.id
        LEFT JOIN expense_reports er ON er.employee_id = e.id
        GROUP BY d.id, d.name
        ORDER BY total_expense DESC
        LIMIT 50
        """
    elif any(keyword in text for keyword in ["還沒核准", "未核准", "尚未核准"]) and any(
        keyword in text for keyword in ["3000", "3,000"]
    ):
        sql = """
        SELECT er.id, e.name AS employee_name, d.name AS department_name,
               er.category, er.amount, er.currency, er.status, er.expense_date,
               er.description
        FROM expense_reports er
        JOIN employees e ON er.employee_id = e.id
        JOIN departments d ON e.department_id = d.id
        WHERE er.status <> 'approved' AND er.amount > 3000
        ORDER BY er.amount DESC
        LIMIT 50
        """
    elif "廠商" in text and any(keyword in text for keyword in ["發票總金額", "發票", "最高"]):
        sql = """
        SELECT COALESCE(v.name, 'Unknown vendor') AS vendor_name,
               SUM(i.total_amount) AS invoice_total
        FROM invoices i
        LEFT JOIN vendors v ON i.vendor_id = v.id
        GROUP BY v.id, v.name
        ORDER BY invoice_total DESC
        LIMIT 50
        """
    else:
        sql = """
        SELECT e.employee_code, e.name, d.name AS department_name,
               e.title, e.email, e.location, e.hire_date
        FROM employees e
        JOIN departments d ON e.department_id = d.id
        ORDER BY e.employee_code
        LIMIT 50
        """

    return GeneratedSql(
        sql=re.sub(r"\s+", " ", sql).strip(),
        reason=reason,
        source="fallback",
    )


def generate_sql(api_key, question, model, schema_description):
    if not api_key:
        return fallback_sql_for_question(question, "OPENAI_API_KEY 未設定，已使用 SQL fallback。")

    try:
        client = create_openai_client(api_key)
        response = client.responses.create(
            model=model,
            instructions=SQL_GENERATOR_PROMPT,
            input=[
                {
                    "role": "user",
                    "content": f"Schema:\n{schema_description}\n\nQuestion:\n{question}",
                }
            ],
            temperature=0,
        )
        generated = parse_generated_sql(response.output_text)
        generated.source = "openai"
        return generated
    except (json.JSONDecodeError, ValidationError) as exc:
        return fallback_sql_for_question(question, f"SQL Generator 輸出不是合法 JSON，已使用 fallback：{exc}")
    except OpenAIError as exc:
        return fallback_sql_for_question(question, f"SQL Generator API 呼叫失敗，已使用 fallback：{sanitize_error(exc, api_key)}")
    except Exception as exc:
        return fallback_sql_for_question(question, f"SQL Generator 發生錯誤，已使用 fallback：{sanitize_error(exc, api_key)}")
