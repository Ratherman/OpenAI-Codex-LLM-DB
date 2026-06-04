import json

from openai import OpenAIError

from app.services.llm_service import create_openai_client, extract_token_usage, sanitize_error

ANSWER_SYNTHESIZER_PROMPT = """
你是 DB Agent Chat 的查詢結果整理器。
請根據使用者問題、SQL、欄位與查詢結果，用繁體中文整理成容易閱讀的回答。

規則：
- 不要編造查詢結果中不存在的資料。
- 如果查無資料，請清楚說明查無符合條件的資料。
- 數字與金額請整理成容易閱讀的格式。
- 可以用條列，但不要輸出冗長解釋。
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

    lines = [f"查詢完成，共找到 {len(rows)} 筆資料："]
    preview_rows = rows[:8]

    for index, row in enumerate(preview_rows, start=1):
        parts = [f"{column}: {format_value(row.get(column))}" for column in columns]
        lines.append(f"{index}. " + "；".join(parts))

    if len(rows) > len(preview_rows):
        lines.append(f"另外還有 {len(rows) - len(preview_rows)} 筆，可展開查詢結果表格查看。")

    return "\n".join(lines)


def synthesize_answer(api_key, question, sql, columns, rows, model, temperature=0.2):
    if not api_key:
        return {"answer": fallback_answer(question, columns, rows), "usage": None, "source": "fallback"}

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
        return {"answer": response.output_text, "usage": extract_token_usage(response), "source": "openai"}
    except OpenAIError as exc:
        return {
            "answer": (
                f"{fallback_answer(question, columns, rows)}\n\n"
                f"LLM 整理失敗，已改用表格摘要：{sanitize_error(exc, api_key)}"
            ),
            "usage": None,
            "source": "fallback",
        }
    except Exception as exc:
        return {
            "answer": (
                f"{fallback_answer(question, columns, rows)}\n\n"
                f"LLM 整理失敗，已改用表格摘要：{sanitize_error(exc, api_key)}"
            ),
            "usage": None,
            "source": "fallback",
        }
