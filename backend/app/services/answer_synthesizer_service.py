import json

from openai import OpenAIError

from app.services.llm_service import create_openai_client, sanitize_error

ANSWER_SYNTHESIZER_PROMPT = """
你是 DB Agent Chat 的資料分析助理。請根據使用者問題、SQL、查詢結果，用繁體中文整理答案。

規則：
- 不要編造查詢結果裡沒有的資料。
- 如果沒有資料，清楚說明沒有找到符合條件的資料。
- 用精簡條列或短段落回答。
- 金額請標示 TWD，必要時加上千分位。
""".strip()


def format_value(value):
    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        return f"{value:,.2f}"
    return str(value)


def fallback_answer(question, columns, rows):
    if not rows:
        return "查詢完成，但沒有找到符合條件的資料。"

    lines = [f"查詢完成，共找到 {len(rows)} 筆資料。"]
    preview_rows = rows[:8]

    for index, row in enumerate(preview_rows, start=1):
        parts = [f"{column}: {format_value(row.get(column))}" for column in columns]
        lines.append(f"{index}. " + "，".join(parts))

    if len(rows) > len(preview_rows):
        lines.append(f"其餘 {len(rows) - len(preview_rows)} 筆可在下方結果表格查看。")

    return "\n".join(lines)


def synthesize_answer(api_key, question, sql, columns, rows, model, temperature=0.2):
    if not api_key:
        return fallback_answer(question, columns, rows)

    try:
        client = create_openai_client(api_key)
        response = client.responses.create(
            model=model,
            instructions=ANSWER_SYNTHESIZER_PROMPT,
            input=[
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "sql": sql,
                            "columns": columns,
                            "rows": rows,
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
            temperature=temperature,
        )
        return response.output_text
    except OpenAIError as exc:
        return f"{fallback_answer(question, columns, rows)}\n\nLLM 整理失敗，已使用基本摘要：{sanitize_error(exc, api_key)}"
    except Exception as exc:
        return f"{fallback_answer(question, columns, rows)}\n\nLLM 整理失敗，已使用基本摘要：{sanitize_error(exc, api_key)}"
