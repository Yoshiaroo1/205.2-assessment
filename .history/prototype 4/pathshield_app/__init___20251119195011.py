from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object('pathshield_app.config.Config')

    # Initialize extensions
    db.init_app(app)

    # Register blueprints
    _register_blueprints(app)

    return app

def _register_blueprints(app):
    """Register all application blueprints"""
    # Main blueprint
    from pathshield_app import routes
    app.register_blueprint(routes.main_bp)
    
    # API blueprint (conditional)
    try:
        from pathshield_app.routes_ai import api_bp
        app.register_blueprint(api_bp, url_prefix='/api')
        app.logger.info("✅ Cost Calculator API routes registered successfully")
    except ImportError as e:
        app.logger.warning(f"⚠️ Cost Calculator API not available: {e}")

