import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object('pathshield_app.config.Config')

    db.init_app(app)

    from pathshield_app import routes
    app.register_blueprint(routes.main_bp)

def register_api_blueprint(app):
    """Register API blueprint if available"""
    try:
        from pathshield_app.routes_api import api_bp
        app.register_blueprint(api_bp)
        print("✅ Cost Calculator API routes registered successfully")
    except ImportError as e:
        print(f"⚠️  Cost Calculator API not available: {e}")

    return app

