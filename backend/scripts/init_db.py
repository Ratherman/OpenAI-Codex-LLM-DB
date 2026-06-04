import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from app.db import Base, get_engine
import app.models  # noqa: F401


def main():
    app = create_app()

    with app.app_context():
        Base.metadata.create_all(bind=get_engine())
        table_names = sorted(Base.metadata.tables.keys())

    print("Initialized database tables:")
    for table_name in table_names:
        print(f"- {table_name}")


if __name__ == "__main__":
    main()
