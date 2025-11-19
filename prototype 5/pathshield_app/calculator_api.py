from flask import Blueprint, request, jsonify

calc_bp = Blueprint('calc', __name__)

@calc_bp.route('/calculate', methods=['POST'])
def calculate():
    data = request.get_json()

    required = ['start_lat', 'start_lon', 'end_lat', 'end_lon']
    missing = [field for field in required if field not in data]

    if missing:
        return jsonify({
            "error": f"Missing required fields: {', '.join(missing)}"
        }), 400

    start_lat = data['start_lat']
    start_lon = data['start_lon']
    end_lat = data['end_lat']
    end_lon = data['end_lon']

    # keep your original fuel price logic
    fuel_price = data.get("fuel_price", 3.20)  # example default

    # do calculation...
    result = {
        "start": (start_lat, start_lon),
        "end": (end_lat, end_lon),
        "fuel_price": fuel_price
    }

    return jsonify(result)


