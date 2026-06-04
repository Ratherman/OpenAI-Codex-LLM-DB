import json
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from app.db import Base, get_engine, get_session
from app.models import KnowledgeChunk
from app.services.llm_service import MissingOpenAIKeyError, create_openai_client, sanitize_error
from sqlalchemy import delete

DATA_PATH = BACKEND_ROOT / "data" / "qa_knowledge.json"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


def load_knowledge_items():
    with DATA_PATH.open("r", encoding="utf-8") as file:
        items = json.load(file)

    if not isinstance(items, list) or not items:
        raise ValueError("qa_knowledge.json must contain a non-empty list.")

    return items


def build_embedding_input(item):
    return "\n".join(
        [
            f"標題：{item['title']}",
            f"分類：{item['category']}",
            f"來源：{item['source']}",
            f"內容：{item['content']}",
        ]
    )


def create_embeddings(api_key, model, inputs):
    client = create_openai_client(api_key)
    response = client.embeddings.create(model=model, input=inputs)
    return [item.embedding for item in response.data]


def main():
    app = create_app()
    api_key = app.config["OPENAI_API_KEY"]
    embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)

    if not api_key:
        print("OPENAI_API_KEY is not configured. Please set it in .env before seeding knowledge embeddings.")
        raise SystemExit(1)

    items = load_knowledge_items()
    inputs = [build_embedding_input(item) for item in items]

    try:
        embeddings = create_embeddings(api_key=api_key, model=embedding_model, inputs=inputs)
    except MissingOpenAIKeyError as exc:
        print(str(exc))
        raise SystemExit(1)
    except Exception as exc:
        print(f"Embedding generation failed: {sanitize_error(exc, api_key)}")
        raise SystemExit(1)

    if len(embeddings) != len(items):
        print("Embedding generation failed: embedding count does not match knowledge item count.")
        raise SystemExit(1)

    with app.app_context():
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        session = get_session()
        try:
            session.execute(delete(KnowledgeChunk))
            for item, embedding in zip(items, embeddings):
                session.add(
                    KnowledgeChunk(
                        title=item["title"],
                        category=item["category"],
                        content=item["content"],
                        source=item["source"],
                        embedding_json=json.dumps(embedding),
                    )
                )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    print(f"Seeded knowledge chunks: {len(items)}")
    print(f"Embedding model: {embedding_model}")


if __name__ == "__main__":
    main()
