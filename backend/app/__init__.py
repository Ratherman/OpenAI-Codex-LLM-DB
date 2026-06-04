from flask import Flask
from flask_cors import CORS

from app.routes.health import health_bp


def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    app.register_blueprint(health_bp)

    return app
