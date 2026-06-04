import json
import math

from openai import OpenAIError
from sqlalchemy import select

from app.models import KnowledgeChunk
from app.services.audit_service import combine_usage
from app.services.llm_service import MissingOpenAIKeyError, create_openai_client, extract_token_usage, sanitize_error

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_TOP_K = 3

RAG_SYNTHESIZER_PROMPT = """
你是公司 MIS / 行政 SOP 助理。請根據提供的 REF 內容回答使用者問題。

規則：
- 使用繁體中文回答。
- 優先引用最相關的 REF。
- 回答中請用 [1] [2] [3] 標示引用來源。
- 不要編造 REF 沒有的政策。
- 如果 REF 不足以回答，請說明不足並建議提交 MIS 或行政工單。
""".strip()


class RagError(RuntimeError):
    pass


def parse_embedding(embedding_json):
    try:
        value = json.loads(embedding_json)
    except json.JSONDecodeError as exc:
        raise RagError("knowledge_chunks 內有無法解析的 embedding_json。") from exc

    if not isinstance(value, list) or not value:
        raise RagError("knowledge_chunks 內有空的 embedding_json。")

    return [float(item) for item in value]


def cosine_similarity(a, b):
    if len(a) != len(b):
        raise RagError("查詢 embedding 與 knowledge embedding 維度不一致，請重新執行 seed_knowledge.py。")

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0
    return dot / (norm_a * norm_b)


def create_query_embedding(api_key, query, embedding_model=DEFAULT_EMBEDDING_MODEL):
    if not api_key:
        raise RagError("OPENAI_API_KEY 未設定，無法產生 RAG 查詢 embedding。請先設定 .env 並重啟後端。")

    try:
        client = create_openai_client(api_key)
        response = client.embeddings.create(model=embedding_model, input=query)
        return response.data[0].embedding, extract_token_usage(response)
    except MissingOpenAIKeyError as exc:
        raise RagError(str(exc)) from exc
    except OpenAIError as exc:
        raise RagError(f"RAG embedding 產生失敗：{sanitize_error(exc, api_key)}") from exc
    except Exception as exc:
        raise RagError(f"RAG embedding 產生失敗：{sanitize_error(exc, api_key)}") from exc


def load_knowledge_chunks(session):
    chunks = session.execute(select(KnowledgeChunk).order_by(KnowledgeChunk.id)).scalars().all()
    if not chunks:
        raise RagError("knowledge_chunks 沒有資料，請先執行 python backend/scripts/seed_knowledge.py。")
    return chunks


def retrieve_top_chunks(session, query_embedding, top_k):
    scored = []
    for chunk in load_knowledge_chunks(session):
        chunk_embedding = parse_embedding(chunk.embedding_json)
        similarity = cosine_similarity(query_embedding, chunk_embedding)
        scored.append((similarity, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[:top_k]


def build_refs(scored_chunks):
    refs = []
    for index, (similarity, chunk) in enumerate(scored_chunks, start=1):
        refs.append(
            {
                "index": index,
                "id": chunk.id,
                "title": chunk.title,
                "category": chunk.category,
                "content": chunk.content,
                "source": chunk.source,
                "similarity": round(float(similarity), 4),
            }
        )
    return refs


def synthesize_rag_answer(api_key, query, refs, model, temperature=0.2):
    if not api_key:
        raise RagError("OPENAI_API_KEY 未設定，無法整理 RAG 回答。請先設定 .env 並重啟後端。")

    ref_text = "\n\n".join(
        f"[{ref['index']}] {ref['title']} ({ref['source']})\n{ref['content']}"
        for ref in refs
    )

    try:
        client = create_openai_client(api_key)
        response = client.responses.create(
            model=model,
            instructions=RAG_SYNTHESIZER_PROMPT,
            input=[
                {
                    "role": "user",
                    "content": f"使用者問題：{query}\n\nREF:\n{ref_text}",
                }
            ],
            temperature=temperature,
        )
        return response.output_text, extract_token_usage(response)
    except OpenAIError as exc:
        raise RagError(f"RAG 回答整理失敗：{sanitize_error(exc, api_key)}") from exc
    except Exception as exc:
        raise RagError(f"RAG 回答整理失敗：{sanitize_error(exc, api_key)}") from exc


def run_rag(session, api_key, query, model, temperature=0.2, top_k=DEFAULT_TOP_K):
    top_k = max(1, min(5, int(top_k or DEFAULT_TOP_K)))
    query_embedding, embedding_usage = create_query_embedding(api_key=api_key, query=query)
    scored_chunks = retrieve_top_chunks(session=session, query_embedding=query_embedding, top_k=top_k)
    refs = build_refs(scored_chunks)
    answer, answer_usage = synthesize_rag_answer(
        api_key=api_key,
        query=query,
        refs=refs,
        model=model,
        temperature=temperature,
    )

    return {
        "route": "RAG",
        "answer": answer,
        "top_k": top_k,
        "refs": refs,
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "usage": combine_usage(embedding_usage, answer_usage),
        "embedding_usage": embedding_usage,
        "answer_usage": answer_usage,
    }
