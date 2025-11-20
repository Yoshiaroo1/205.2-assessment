from flask import Flask, request, jsonify
from functools import lru_cache
from typing import Tuple, Dict
import numpy as np
import logging

app = Flask(__name__)

class AucklandDrivingCostCalculator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # Fuel prices
        self.fuel_prices = {
            '91_unleaded': 2.85,
            '95_premium': 3.05,
            '98_premium': 3.15,
            'diesel': 2.45,
            'ev_charging': 0.28
        }

        # Vehicle efficiency (km per liter or km per kWh)
        self.vehicle_efficiency = {
            'small_car': 15.0,
            'medium_car': 12.0,
            'large_car': 9.0,
            'suv': 10.0,
            'truck_ute': 8.0,
            'ev_small': 6.5,
            'ev_medium': 5.5,
            'ev_large': 4.5
        }

        # Auckland operating costs
        self.auckland_costs = {
            'hourly_wage': 25.0,
            'vehicle_depreciation': 0.15,
            'maintenance_cost': 0.08,
            'insurance_cost': 0.05,
            'registration_cost': 0.03,
            'parking_downtown': 8.0,
            'parking_suburban': 3.0,
        }

        # Toll roads
        self.toll_roads = {
            'northern_gateway': 2.40,
            'takaanini_tunnel': 2.10
        }

        # Traffic speed multipliers
        self.traffic_patterns = {
            'early_morning': {'speed_multiplier': 1.2},
            'morning_peak': {'speed_multiplier': 0.6},
            'midday': {'speed_multiplier': 0.9},
            'afternoon_peak': {'speed_multiplier': 0.7},
            'evening': {'speed_multiplier': 1.1},
            'late_night': {'speed_multiplier': 1.3}
        }

        self.base_speed = 50.0

    @lru_cache(maxsize=128)
    def calculate_distance(self, start_coords: Tuple[float, float], end_coords: Tuple[float, float]) -> float:
        lat1, lon1 = start_coords
        lat2, lon2 = end_coords

        R = 6371
        dlat = np.radians(lat2 - lat1)
        dlon = np.radians(lon2 - lon1)

        a = (np.sin(dlat / 2)**2 +
             np.cos(np.radians(lat1)) *
             np.cos(np.radians(lat2)) *
             np.sin(dlon / 2)**2)

        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        return R * c

    def estimate_travel_time(self, distance_km: float, time_of_day: str, route_efficiency: float):
        if time_of_day not in self.traffic_patterns:
            time_of_day = 'midday'

        multiplier = self.traffic_patterns[time_of_day]['speed_multiplier']
        adjusted_speed = self.base_speed * multiplier * route_efficiency

        travel_time_hours = distance_km / adjusted_speed
        travel_time_minutes = travel_time_hours * 60

        return {
            "travel_time_hours": round(travel_time_hours, 2),
            "travel_time_minutes": round(travel_time_minutes, 2),
            "average_speed_kmh": round(adjusted_speed, 1)
        }

    def calculate_fuel_cost(self, distance_km, vehicle_type, fuel_type):
        efficiency = self.vehicle_efficiency[vehicle_type]

        if vehicle_type.startswith("ev_"):
            kwh_used = distance_km / efficiency
            cost = kwh_used * self.fuel_prices[fuel_type]
            return {
                "fuel_cost": round(cost, 2),
                "fuel_used_liters": 0,
                "kwh_used": round(kwh_used, 2)
            }

        fuel_liters = distance_km / efficiency
        cost = fuel_liters * self.fuel_prices[fuel_type]

        return {
            "fuel_cost": round(cost, 2),
            "fuel_used_liters": round(fuel_liters, 2),
            "kwh_used": 0
        }

    def estimate_toll_costs(self, start_coords, end_coords):
        toll_cost = 0
        start_lat, start_lon = start_coords
        end_lat, end_lon = end_coords

        # Very basic bounding box check
        northern_gateway_bounds = {
            "min_lat": -36.9, "max_lat": -36.6,
            "min_lon": 174.4, "max_lon": 174.8
        }

        start_in = (northern_gateway_bounds["min_lat"] <= start_lat <= northern_gateway_bounds["max_lat"] and
                    northern_gateway_bounds["min_lon"] <= start_lon <= northern_gateway_bounds["max_lon"])

        end_in = (northern_gateway_bounds["min_lat"] <= end_lat <= northern_gateway_bounds["max_lat"] and
                  northern_gateway_bounds["min_lon"] <= end_lon <= northern_gateway_bounds["max_lon"])

        if start_in or end_in:
            toll_cost += self.toll_roads["northern_gateway"]

        return toll_cost

    def calculate_driving_cost(self, start_coords, end_coords, vehicle_type, fuel_type,
                               time_of_day, include_parking, parking_duration_hours,
                               include_tolls, route_efficiency):

        distance_km = self.calculate_distance(start_coords, end_coords)
        time_est = self.estimate_travel_time(distance_km, time_of_day, route_efficiency)
        fuel = self.calculate_fuel_cost(distance_km, vehicle_type, fuel_type)

        time_cost = time_est["travel_time_hours"] * self.auckland_costs["hourly_wage"]

        operating_costs = distance_km * (
            self.auckland_costs["vehicle_depreciation"] +
            self.auckland_costs["maintenance_cost"] +
            self.auckland_costs["insurance_cost"] +
            self.auckland_costs["registration_cost"]
        )

        parking_cost = 0
        if include_parking:
            parking_cost = self.auckland_costs["parking_downtown"] * parking_duration_hours

        toll_cost = self.estimate_toll_costs(start_coords, end_coords) if include_tolls else 0

        total_cost = fuel["fuel_cost"] + time_cost + operating_costs + parking_cost + toll_cost

        return {
            "distance_km": round(distance_km, 2),
            "total_cost": round(total_cost, 2),
            "cost_per_km": round(total_cost / distance_km, 2),
            **time_est,
            **fuel,
            "operating_costs": round(operating_costs, 2),
            "parking_cost": round(parking_cost, 2),
            "toll_cost": round(toll_cost, 2)
        }

    def compare_vehicles(self, start_coords, end_coords, time_of_day):
        vehicles = [
            ("small_car", "91_unleaded"),
            ("medium_car", "91_unleaded"),
            ("suv", "91_unleaded"),
            ("ev_medium", "ev_charging")
        ]

        results = []
        for v, f in vehicles:
            cost = self.calculate_driving_cost(start_coords, end_coords, v, f,
                                               time_of_day, False, 0, True, 1.0)
            results.append({
                "vehicle_type": v,
                "fuel_type": f,
                "total_cost": cost["total_cost"],
                "cost_per_km": cost["cost_per_km"]
            })

        results.sort(key=lambda x: x["total_cost"])
        return {"optimal_vehicle": results[0], "all_vehicles": results}


calculator = AucklandDrivingCostCalculator()

# ---------------------------
# API ROUTES
# ---------------------------

@app.route("/calculate", methods=["POST"])
def api_calculate_cost():
    data = request.get_json()

    result = calculator.calculate_driving_cost(
        tuple(data["start_coords"]),
        tuple(data["end_coords"]),
        data.get("vehicle_type", "medium_car"),
        data.get("fuel_type", "91_unleaded"),
        data.get("time_of_day", "midday"),
        data.get("include_parking", False),
        data.get("parking_duration_hours", 2.0),
        data.get("include_tolls", True),
        data.get("route_efficiency", 1.0)
    )

    return jsonify(result)


@app.route("/compare", methods=["POST"])
def api_compare_vehicles():
    data = request.get_json()

    result = calculator.compare_vehicles(
        tuple(data["start_coords"]),
        tuple(data["end_coords"]),
        data.get("time_of_day", "midday")
    )

    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
