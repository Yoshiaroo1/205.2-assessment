from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from pathshield_app import db
from pathshield_app.models import User, RouteData
from pathshield_app.routes_ai import generate_route
from werkzeug.security import generate_password_hash, check_password_hash

# ---------- Blueprint ----------
main_bp = Blueprint("main", __name__)

# ---------- PUBLIC ROUTES ----------

@main_bp.route("/")
def home():
    return render_template("index.html")

@main_bp.route("/about")
def about():
    return render_template("about.html")

@main_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if not username or not email or not password:
            flash("Please fill out all fields.", "warning")
            return redirect(url_for("main.register"))

        hashed_password = generate_password_hash(password)

        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash("Account created successfully! Please login.", "success")
        return redirect(url_for("main.login"))

    return render_template("register.html")

@main_bp.route("/preferences", methods=["GET", "POST"])
def preferences():
    if "user_id" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("main.login"))
    return render_template("preferences.html", username=session.get("username"))
    



@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["username"] = user.username
            flash("Logged in successfully!", "success")
            return redirect(url_for("main.dashboard"))
        else:
            flash("Invalid email or password.", "danger")

    return render_template("login.html")

@main_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.home"))

# ---------- DASHBOARD ----------

@main_bp.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("main.login"))
    return render_template("dashboard.html", username=session.get("username"))

# ---------- MAP / ROUTE ----------

@main_bp.route("/map", methods=["GET", "POST"])
def map_view():
    if "user_id" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("main.login"))

    route_info = None
    
    if request.method == "POST":
        start = request.form.get("start")
        end = request.form.get("end")
        mode = request.form.get("mode", "pedestrian")

        if start and end:
            route_info = generate_route(start, end, mode)

            # Save route to database
            new_route = RouteData(
                start_point=start,
                end_point=end,
                travel_mode=mode
            )
            db.session.add(new_route)
            db.session.commit()
            
            #redirect to the map display page with the generated map
            return render_template("route_map.html")
            
        else:
            flash("Please provide both start and end locations.", "warning")

    return render_template("map.html", route=route_info)

