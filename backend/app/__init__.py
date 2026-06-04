from flask import Flask
from flask_cors import CORS

from app.config import load_config
from app.db import init_db
from app.routes.chat import chat_bp
from app.routes.chat_rooms import chat_rooms_bp
from app.routes.company_data import company_data_bp
from app.routes.db_health import db_health_bp
from app.routes.health import health_bp
from app.routes.llm_health import llm_health_bp


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

    return app
