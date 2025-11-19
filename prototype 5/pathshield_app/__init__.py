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
    from pathshield_app import routes
    app.register_blueprint(routes.main_bp)
    
    # 🔥 Register the calculator API blueprint
    from pathshield_app.calculator_api import calc_bp
    app.register_blueprint(calc_bp)

    return app
