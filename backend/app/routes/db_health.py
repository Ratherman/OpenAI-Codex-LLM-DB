from flask import Blueprint, jsonify
from sqlalchemy.exc import SQLAlchemyError

from app.db import check_database_connection

db_health_bp = Blueprint("db_health", __name__)


@db_health_bp.get("/api/db/health")
def db_health_check():
    try:
        version = check_database_connection()
    except SQLAlchemyError as exc:
        return (
            jsonify(
                {
                    "status": "error",
                    "database": {"connected": False},
                    "error": str(exc),
                }
            ),
            503,
        )
    except Exception as exc:
        return (
            jsonify(
                {
                    "status": "error",
                    "database": {"connected": False},
                    "error": str(exc),
                }
            ),
            503,
        )

    return jsonify(
        {
            "status": "ok",
            "database": {
                "connected": True,
                "version": version,
            },
        }
    )
