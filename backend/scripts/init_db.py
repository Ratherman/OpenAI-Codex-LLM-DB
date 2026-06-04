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


def ensure_audit_logs_schema(engine):
    inspector = inspect(engine)
    if "audit_logs" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("audit_logs")}
    column_defs = {
        "room_id": "INT NULL",
        "action_type": "VARCHAR(120) NULL",
        "route": "VARCHAR(80) NULL",
        "model": "VARCHAR(120) NULL",
        "input_summary": "TEXT NULL",
        "output_summary": "TEXT NULL",
        "sql_text": "TEXT NULL",
        "db_table": "VARCHAR(120) NULL",
        "db_record_id": "VARCHAR(80) NULL",
        "prompt_tokens": "INT NULL",
        "completion_tokens": "INT NULL",
        "total_tokens": "INT NULL",
        "metadata_json": "TEXT NULL",
    }

    with engine.begin() as connection:
        for column_name, column_type in column_defs.items():
            if column_name not in columns:
                connection.execute(text(f"ALTER TABLE audit_logs ADD COLUMN {column_name} {column_type}"))

        for legacy_column, column_type in {
            "actor": "VARCHAR(120) NULL",
            "action": "VARCHAR(120) NULL",
            "target_type": "VARCHAR(80) NULL",
            "details": "TEXT NULL",
        }.items():
            if legacy_column in columns:
                connection.execute(text(f"ALTER TABLE audit_logs MODIFY {legacy_column} {column_type}"))

        connection.execute(text("UPDATE audit_logs SET action_type = COALESCE(action_type, action, 'system')"))
        connection.execute(text("UPDATE audit_logs SET route = COALESCE(route, target_type, 'system')"))
        connection.execute(text("UPDATE audit_logs SET metadata_json = COALESCE(metadata_json, details, '{}')"))
        connection.execute(text("ALTER TABLE audit_logs MODIFY action_type VARCHAR(120) NOT NULL"))
        connection.execute(text("ALTER TABLE audit_logs MODIFY route VARCHAR(80) NOT NULL"))
        connection.execute(text("ALTER TABLE audit_logs MODIFY metadata_json TEXT NOT NULL"))


def main():
    app = create_app()

    with app.app_context():
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        ensure_chat_messages_metadata_json(engine)
        ensure_audit_logs_schema(engine)
        table_names = sorted(Base.metadata.tables.keys())

    print("Initialized database tables:")
    for table_name in table_names:
        print(f"- {table_name}")


if __name__ == "__main__":
    main()
