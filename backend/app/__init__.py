from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import RequestEntityTooLarge

from app.config import load_config
from app.db import init_db
from app.routes.chat import chat_bp
from app.routes.chat_rooms import chat_rooms_bp
from app.routes.company_data import company_data_bp
from app.routes.db_health import db_health_bp
from app.routes.health import health_bp
from app.routes.llm_health import llm_health_bp
from app.routes.uploads import uploads_bp


def create_app():
    app = Flask(__name__)
    load_config(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    init_db(app)

    app.register_blueprint(chat_bp)
    app.register_blueprint(chat_rooms_bp)
    app.register_blueprint(company_data_bp)
    app.register_blueprint(db_health_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(llm_health_bp)
    app.register_blueprint(uploads_bp)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_upload_too_large(_error):
        max_mb = app.config["MAX_IMAGE_UPLOAD_BYTES"] // (1024 * 1024)
        return jsonify({"status": "error", "error": f"圖片太大，請上傳 {max_mb}MB 以內的檔案。"}), 413

    return app
