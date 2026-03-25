import os
from flask import Flask
from app.config import Config
from app.database import init_db, get_db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Ensure data directory exists
    db_path = app.config["DATABASE_PATH"]
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Initialize database on first request
    with app.app_context():
        init_db(db_path)

    # Register teardown to close DB connections
    @app.teardown_appcontext
    def close_connection(exception):
        db = get_db(close=True)

    # Register blueprints
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.admin import bp as admin_bp
    from app.routes.api import bp as api_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    return app
