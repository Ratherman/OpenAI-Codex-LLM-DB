from openai import OpenAI


def generate_reply(api_key, message, model, system_prompt, temperature):
    if not api_key:
        return {
            "provider": "mock",
            "model": model,
            "message": f"我收到你的訊息了：{message}。目前前端指定模型是 {model}。下一階段會串接後端與 LLM。",
        }

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt or "你是一個實用、精準的 AI 助手。"},
            {"role": "user", "content": message},
        ],
        temperature=temperature,
    )

    return {
        "provider": "openai",
        "model": model,
        "message": response.output_text,
    }
