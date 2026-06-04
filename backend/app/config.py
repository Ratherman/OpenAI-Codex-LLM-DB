import os
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_DATABASE_URL = "mysql+pymysql://codex_user:codex_pass@127.0.0.1:3306/codex_demo"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
DEFAULT_MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024


def load_config(app):
    load_dotenv(PROJECT_ROOT / ".env")

    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_api_key == "請填入你的 key":
        openai_api_key = ""

    app.config["DATABASE_URL"] = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    app.config["OPENAI_API_KEY"] = openai_api_key
    app.config["UPLOAD_FOLDER"] = os.getenv("UPLOAD_FOLDER", str(BACKEND_ROOT / "uploads"))
    app.config["MAX_IMAGE_UPLOAD_BYTES"] = int(
        os.getenv("MAX_IMAGE_UPLOAD_BYTES", DEFAULT_MAX_IMAGE_UPLOAD_BYTES)
    )
    app.config["MAX_CONTENT_LENGTH"] = app.config["MAX_IMAGE_UPLOAD_BYTES"]
