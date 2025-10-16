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

    return app
