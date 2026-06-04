import re


UNSAFE_PATTERNS = [
    r"\bdrop\s+table\b",
    r"\btruncate\b",
    r"\bdelete\s+from\b",
    r"\bupdate\s+\w+\s+set\b",
    r"\binsert\s+into\b",
    r"刪除所有",
    r"刪掉所有",
    r"清空",
    r"刪除.*資料",
    r"刪除.*費用",
    r"忽略.*系統提示",
    r"忽略.*指令",
    r"ignore.*system",
    r"bypass.*instruction",
]


def detect_unsafe_request(message):
    text = str(message or "").strip()
    lower_text = text.lower()

    for pattern in UNSAFE_PATTERNS:
        if re.search(pattern, lower_text, flags=re.IGNORECASE):
            return {
                "blocked": True,
                "reason": "這個請求包含刪除、覆寫資料、繞過系統提示或直接執行危險 SQL 的意圖。",
                "matched_pattern": pattern,
            }

    return {"blocked": False, "reason": "", "matched_pattern": ""}


def build_security_refusal(reason):
    return (
        "我不能執行這個操作，因為它可能刪除或破壞資料，或要求我繞過系統安全規則。\n\n"
        f"原因：{reason}\n\n"
        "這個教學系統的安全邊界是：DB Query 只能執行 SELECT；DB Write 只能透過白名單工具，"
        "而且需要使用者確認後才會寫入。若你只是想查看資料，請改成查詢需求，例如："
        "「列出目前所有費用資料」。"
    )
