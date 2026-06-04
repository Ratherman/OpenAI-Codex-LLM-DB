import re
from dataclasses import dataclass

from app.services.schema_introspection_service import ALLOWED_QUERY_TABLES

MAX_QUERY_LIMIT = 50
FORBIDDEN_TABLES = {"chat_rooms", "chat_messages", "audit_logs"}
FORBIDDEN_KEYWORDS = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "replace",
    "merge",
    "call",
    "exec",
    "execute",
    "grant",
    "revoke",
    "lock",
    "unlock",
    "load",
)
FORBIDDEN_PATTERNS = (
    r"\binto\b",
    r"\boutfile\b",
    r"\bdumpfile\b",
    r"\bload_file\s*\(",
    r"\bsleep\s*\(",
    r"\bbenchmark\s*\(",
    r"\binformation_schema\b",
    r"\bperformance_schema\b",
    r"\bmysql\b\s*\.",
    r"\bsys\b\s*\.",
)


class SqlValidationError(ValueError):
    pass


@dataclass
class ValidationResult:
    sql: str
    warnings: list[str]


def strip_code_fence(sql):
    cleaned = str(sql or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:sql)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    return cleaned


def normalize_sql(sql):
    cleaned = strip_code_fence(sql)
    if not cleaned:
        raise SqlValidationError("SQL 不可為空。")

    if "--" in cleaned or "/*" in cleaned or "*/" in cleaned or "#" in cleaned:
        raise SqlValidationError("SQL 不可包含註解。")

    without_trailing_semicolon = cleaned.rstrip().removesuffix(";").strip()
    if ";" in without_trailing_semicolon:
        raise SqlValidationError("不允許多語句 SQL。")

    return re.sub(r"\s+", " ", without_trailing_semicolon).strip()


def enforce_limit(sql, max_limit=MAX_QUERY_LIMIT):
    warnings = []
    limit_match = re.search(r"\blimit\s+(\d+)\s*$", sql, flags=re.IGNORECASE)

    if not limit_match:
        return f"{sql} LIMIT {max_limit}", [f"已自動加上 LIMIT {max_limit}。"]

    limit_value = int(limit_match.group(1))
    if limit_value <= max_limit:
        return sql, warnings

    capped_sql = re.sub(
        r"\blimit\s+\d+\s*$",
        f"LIMIT {max_limit}",
        sql,
        flags=re.IGNORECASE,
    )
    warnings.append(f"LIMIT 已從 {limit_value} 限制為 {max_limit}。")
    return capped_sql, warnings


def validate_select_sql(sql, max_limit=MAX_QUERY_LIMIT):
    normalized = normalize_sql(sql)
    lowered = normalized.lower()

    if not re.match(r"^\s*select\b", lowered):
        raise SqlValidationError("只允許 SELECT 查詢。")

    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", lowered):
            raise SqlValidationError(f"SQL 包含禁止的關鍵字：{keyword.upper()}。")

    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, lowered):
            raise SqlValidationError("SQL 包含不允許的語法或系統物件。")

    for forbidden_table in FORBIDDEN_TABLES:
        if re.search(rf"\b{forbidden_table}\b", lowered):
            raise SqlValidationError(f"不允許查詢資料表：{forbidden_table}。")

    table_refs = re.findall(r"\b(?:from|join)\s+`?([a-zA-Z_][\w]*)`?", lowered)
    if not table_refs:
        raise SqlValidationError("SQL 必須查詢允許的業務資料表。")

    for table in table_refs:
        if table not in ALLOWED_QUERY_TABLES:
            raise SqlValidationError(f"不允許查詢資料表：{table}。")

    safe_sql, warnings = enforce_limit(normalized, max_limit=max_limit)
    return ValidationResult(sql=safe_sql, warnings=warnings)
