import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from app.db import Base, get_engine
import app.models  # noqa: F401
from sqlalchemy import inspect, text


def ensure_chat_messages_metadata_json(engine):
    inspector = inspect(engine)
    if "chat_messages" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("chat_messages")}
    if "metadata_json" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE chat_messages ADD COLUMN metadata_json TEXT NULL"))
        connection.execute(text("UPDATE chat_messages SET metadata_json = '{}' WHERE metadata_json IS NULL"))
        connection.execute(text("ALTER TABLE chat_messages MODIFY metadata_json TEXT NOT NULL"))


def main():
    app = create_app()

    with app.app_context():
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        ensure_chat_messages_metadata_json(engine)
        table_names = sorted(Base.metadata.tables.keys())

    print("Initialized database tables:")
    for table_name in table_names:
        print(f"- {table_name}")


if __name__ == "__main__":
    main()
