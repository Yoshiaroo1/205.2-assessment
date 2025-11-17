from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from pathshield_app import db
from pathshield_app.models import User, RouteData
from pathshield_app.routes_ai import generate_route
from werkzeug.security import generate_password_hash, check_password_hash
from pathshield_app.cost_calculator import cost_calculator

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
        else:
            flash("Please provide both start and end locations.", "warning")

    return render_template("route_map.html", route=route_info)

# ---------- COST CALCULATOR API ROUTES ----------

@main_bp.route('/api/calculate-cost', methods=['POST'])
def calculate_driving_cost():
    """Calculate driving cost for a route"""
    try:
        data = request.get_json()
        
        # Extract parameters
        start_coords = tuple(data.get('start_coords'))
        end_coords = tuple(data.get('end_coords'))
        vehicle_type = data.get('vehicle_type', 'medium_car')
        fuel_type = data.get('fuel_type', '91_unleaded')
        time_of_day = data.get('time_of_day', 'midday')
        include_parking = data.get('include_parking', False)
        parking_duration = data.get('parking_duration_hours', 2.0)
        
        # Calculate cost
        result = cost_calculator.calculate_driving_cost(
            start_coords=start_coords,
            end_coords=end_coords,
            vehicle_type=vehicle_type,
            fuel_type=fuel_type,
            time_of_day=time_of_day,
            include_parking=include_parking,
            parking_duration_hours=parking_duration
        )
        
        return {'success': True, 'data': result}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}, 400

@main_bp.route('/api/compare-vehicles', methods=['POST'])
def compare_vehicles():
    """Compare costs across different vehicle types"""
    try:
        data = request.get_json()
        start_coords = tuple(data.get('start_coords'))
        end_coords = tuple(data.get('end_coords'))
        time_of_day = data.get('time_of_day', 'midday')
        
        result = cost_calculator.compare_vehicles(
            start_coords, end_coords, time_of_day
        )
        
        return {'success': True, 'data': result}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}, 400

@main_bp.route('/api/vehicle-options', methods=['GET'])
def get_vehicle_options():
    """Get available vehicle and fuel options"""
    options = {
        'vehicle_types': [
            {'value': 'small_car', 'label': 'Small Car'},
            {'value': 'medium_car', 'label': 'Medium Car'},
            {'value': 'large_car', 'label': 'Large Car'},
            {'value': 'suv', 'label': 'SUV'},
            {'value': 'truck_ute', 'label': 'Truck/Ute'},
            {'value': 'ev_small', 'label': 'Small EV'},
            {'value': 'ev_medium', 'label': 'Medium EV'},
            {'value': 'ev_large', 'label': 'Large EV'}
        ],
        'fuel_types': [
            {'value': '91_unleaded', 'label': '91 Unleaded'},
            {'value': '95_premium', 'label': '95 Premium'},
            {'value': '98_premium', 'label': '98 Premium'},
            {'value': 'diesel', 'label': 'Diesel'},
            {'value': 'ev_charging', 'label': 'EV Charging'}
        ],
        'time_slots': [
            {'value': 'early_morning', 'label': 'Early Morning (4:00-6:00)'},
            {'value': 'morning_peak', 'label': 'Morning Peak (6:00-9:00)'},
            {'value': 'midday', 'label': 'Midday (9:00-15:00)'},
            {'value': 'afternoon_peak', 'label': 'Afternoon Peak (15:00-18:00)'},
            {'value': 'evening', 'label': 'Evening (18:00-22:00)'},
            {'value': 'late_night', 'label': 'Late Night (22:00-4:00)'}
        ]
    }
    
    return {'success': True, 'data': options}

# ---------- MODIFIED ROUTE MAP WITH COST PANEL ----------

@main_bp.route("/route_map_with_costs")
def route_map_with_costs():
    """Route map with integrated cost calculator panel"""
    if "user_id" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("main.login"))

    route_info = None

    return render_template("route_map.html", route=route_info)
