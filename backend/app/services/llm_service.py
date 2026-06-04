from openai import OpenAI
from openai import OpenAIError


class MissingOpenAIKeyError(RuntimeError):
    pass


def mask_api_key(api_key):
    if not api_key:
        return None

    if len(api_key) <= 8:
        return "***"

    return f"{api_key[:3]}...{api_key[-4:]}"


def sanitize_error(error, api_key=None):
    message = str(error)
    if api_key:
        message = message.replace(api_key, mask_api_key(api_key) or "***")
    return message


def create_openai_client(api_key):
    if not api_key:
        raise MissingOpenAIKeyError("OPENAI_API_KEY is not configured. Please set it in .env and restart the backend.")

    return OpenAI(api_key=api_key, timeout=20.0)


def check_llm_health(api_key):
    masked_key = mask_api_key(api_key)

    if not api_key:
        return {
            "configured": False,
            "api_reachable": False,
            "key_masked": None,
            "error": "OPENAI_API_KEY is not configured. Please set it in .env and restart the backend.",
        }

    try:
        client = create_openai_client(api_key)
        models = client.models.list()
        sample_model_ids = [model.id for model in models.data[:5]]
    except OpenAIError as exc:
        return {
            "configured": True,
            "api_reachable": False,
            "key_masked": masked_key,
            "error": f"OpenAI API health check failed: {sanitize_error(exc, api_key)}",
        }
    except Exception as exc:
        return {
            "configured": True,
            "api_reachable": False,
            "key_masked": masked_key,
            "error": f"OpenAI API health check failed: {sanitize_error(exc, api_key)}",
        }

    return {
        "configured": True,
        "api_reachable": True,
        "key_masked": masked_key,
        "sample_models": sample_model_ids,
        "error": "",
    }


def build_input_messages(history, message):
    input_messages = []

    for history_message in history:
        if history_message.role not in {"user", "assistant"}:
            continue

        input_messages.append(
            {
                "role": history_message.role,
                "content": history_message.content,
            }
        )

    input_messages.append({"role": "user", "content": message})
    return input_messages


def select_recent_memory_rounds(history, memory_rounds):
    selected_messages = []
    completed_rounds = 0
    has_assistant_in_current_round = False

    for history_message in reversed(history):
        if history_message.role not in {"user", "assistant"}:
            continue

        selected_messages.append(history_message)

        if history_message.role == "assistant":
            has_assistant_in_current_round = True
        elif history_message.role == "user":
            completed_rounds += 1
            has_assistant_in_current_round = False
            if completed_rounds >= memory_rounds:
                break

    if selected_messages and completed_rounds < memory_rounds and has_assistant_in_current_round:
        completed_rounds += 1

    return list(reversed(selected_messages))


def generate_reply(api_key, message, model, system_prompt, temperature, history=None, memory_rounds=5):
    client = create_openai_client(api_key)
    selected_history = select_recent_memory_rounds(history or [], memory_rounds)
    input_messages = build_input_messages(selected_history, message)

    response = client.responses.create(
        model=model,
        instructions=system_prompt or "你是一個實用、精準的 AI 助手。",
        input=input_messages,
        temperature=temperature,
    )

    return {
        "provider": "openai",
        "model": model,
        "message": response.output_text,
        "response_id": response.id,
        "memory_rounds": memory_rounds,
        "memory_message_count": len(selected_history),
    }
