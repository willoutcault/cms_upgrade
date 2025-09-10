import os
from flask import Flask, redirect, url_for
from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine import Engine

from .extensions import db, init_readonly_engine_from_env
from .routes.campaigns import campaigns_bp
from .routes.api import api_bp
from .routes.targets import targets_bp

# Only enable PRAGMA on SQLite connections
try:
    from sqlite3 import Connection as SQLite3Connection
except Exception:
    SQLite3Connection = None

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if SQLite3Connection and isinstance(dbapi_connection, SQLite3Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

def create_app():
    load_dotenv()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-not-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///campaigns.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    init_readonly_engine_from_env()

    # Blueprints
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(targets_bp)

    @app.route("/")
    def index():
        return redirect(url_for("campaigns.list_campaigns"))

    return app
