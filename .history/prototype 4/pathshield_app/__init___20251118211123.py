try:
    from pathshield_app import routes
    app.register_blueprint(routes.main_bp)
except ImportError as e:
    app.logger.error(f"Failed to register main blueprint: {e}")
    raise