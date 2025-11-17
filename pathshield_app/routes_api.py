# pathshield_app/api_routes.py
from flask import Blueprint, jsonify, request
from cost_calculator import cost_calculator

# Create API Blueprint
api_bp = Blueprint('api', __name__)

@api_bp.route('/api/calculate-cost', methods=['POST'])
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
        
        return jsonify({'success': True, 'data': result})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@api_bp.route('/api/compare-vehicles', methods=['POST'])
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
        
        return jsonify({'success': True, 'data': result})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@api_bp.route('/api/vehicle-options', methods=['GET'])
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
    
    return jsonify({'success': True, 'data': options})