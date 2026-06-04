from flask import current_app
from sqlalchemy import create_engine, text


def init_db(app):
    database_url = app.config["DATABASE_URL"]
    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    app.extensions["db_engine"] = engine


def get_engine():
    return current_app.extensions["db_engine"]


def check_database_connection():
    engine = get_engine()

    with engine.connect() as connection:
        version = connection.execute(text("SELECT VERSION()")).scalar_one()

    return version
