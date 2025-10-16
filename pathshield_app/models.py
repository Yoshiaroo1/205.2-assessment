from pathshield_app import db

# ---------- USER MODEL ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)

    def __repr__(self):
        return f"<User {self.username}>"

# ---------- ROUTE DATA MODEL ----------
class RouteData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_point = db.Column(db.String(255), nullable=False)
    end_point = db.Column(db.String(255), nullable=False)
    travel_mode = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f"<Route {self.start_point} → {self.end_point}>"
