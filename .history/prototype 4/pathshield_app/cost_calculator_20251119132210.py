import geopandas as gpd
import pandas as pd
import json
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from functools import lru_cache

class AucklandDrivingCostCalculator:
    """
    Driving cost calculator for Auckland, NZ
    Integrated into Pathshield Flask app
    """
    
    def __init__(self):
        import logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        """
        Initialize the driving cost calculator with Auckland-specific data
        """
        # Current fuel prices in Auckland (NZD per liter)
        self.fuel_prices = {
            '91_unleaded': 2.85,
            '95_premium': 3.05,
            '98_premium': 3.15,
            'diesel': 2.45,
            'ev_charging': 0.28
        }
        
        # Vehicle efficiency (km per liter or km per kWh for EVs)
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
        
        # Auckland-specific costs (NZD)
        self.auckland_costs = {
            'hourly_wage': 25.0,
            'vehicle_depreciation': 0.15,
            'maintenance_cost': 0.08,
            'insurance_cost': 0.05,
            'registration_cost': 0.03, 
            'parking_downtown': 8.0,
            'parking_suburban': 3.0,
        }
        
        # Auckland toll roads
        self.toll_roads = {
            'northern_gateway': 2.40,
            'takaanini_tunnel': 2.10
        }
        
        # Traffic patterns (average speed multipliers by time of day)
        self.traffic_patterns = {
            'early_morning': {'speed_multiplier': 1.2, 'hours': '4:00-6:00'},
            'morning_peak': {'speed_multiplier': 0.6, 'hours': '6:00-9:00'},
            'midday': {'speed_multiplier': 0.9, 'hours': '9:00-15:00'},
            'afternoon_peak': {'speed_multiplier': 0.7, 'hours': '15:00-18:00'},
            'evening': {'speed_multiplier': 1.1, 'hours': '18:00-22:00'},
            'late_night': {'speed_multiplier': 1.3, 'hours': '22:00-4:00'}
        }

        self.base_speed = 50.0
    
    @lru_cache(maxsize=128)
    def calculate_distance(self, start_coords: Tuple[float, float], 
                          end_coords: Tuple[float, float]) -> float:
        """
        Calculate driving distance between two points in kilometers
        Uses Haversine formula for great-circle distance
        """
        lat1, lon1 = start_coords
        lat2, lon2 = end_coords
        
        R = 6371
        
        dlat = np.radians(lat2 - lat1)
        dlon = np.radians(lon2 - lon1)
        
        a = (np.sin(dlat/2) * np.sin(dlat/2) + 
             np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * 
             np.sin(dlon/2) * np.sin(dlon/2))
        
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
        distance_km = R * c
        
        return distance_km
    
    def estimate_travel_time(self, distance_km: float, 
                           time_of_day: str = 'midday',
                           route_efficiency: float = 1.0) -> Dict:
        """
        Estimate travel time based on distance and traffic conditions
        """
        if time_of_day not in self.traffic_patterns:
            time_of_day = 'midday'

        traffic_multiplier = self.traffic_patterns[time_of_day]['speed_multiplier']
        adjusted_speed = self.base_speed * traffic_multiplier * route_efficiency

        travel_time_hours = distance_km / adjusted_speed
        travel_time_minutes = travel_time_hours * 60
        
        return {
            'travel_time_hours': round(travel_time_hours, 2),
            'travel_time_minutes': round(travel_time_minutes, 2),
            'average_speed_kmh': round(adjusted_speed, 1),
            'time_of_day': time_of_day
        }
    
    def calculate_fuel_cost(self, distance_km: float, 
                          vehicle_type: str, 
                          fuel_type: str) -> Dict:
        """
        Calculate fuel/electricity cost for a journey
        """
        if vehicle_type not in self.vehicle_efficiency:
            raise ValueError(f"Unknown vehicle type: {vehicle_type}")
        
        if fuel_type not in self.fuel_prices:
            raise ValueError(f"Unknown fuel type: {fuel_type}")
        
        efficiency = self.vehicle_efficiency[vehicle_type]
        
        if vehicle_type.startswith('ev_'):
            kwh_used = distance_km / efficiency
            fuel_cost = kwh_used * self.fuel_prices[fuel_type]
            fuel_used_liters = 0
            cost_per_km = fuel_cost / distance_km
        else:
            fuel_used_liters = distance_km / efficiency
            fuel_cost = fuel_used_liters * self.fuel_prices[fuel_type]
            kwh_used = 0
            cost_per_km = fuel_cost / distance_km
        
        return {
            'fuel_cost': round(fuel_cost, 2),
            'fuel_used_liters': round(fuel_used_liters, 2),
            'kwh_used': round(kwh_used, 2),
            'efficiency': efficiency,
            'cost_per_km': round(cost_per_km, 2),
            'vehicle_type': vehicle_type,
            'fuel_type': fuel_type
        }
    
    def calculate_driving_cost(self,
                             start_coords: Tuple[float, float],
                             end_coords: Tuple[float, float],
                             vehicle_type: str = 'medium_car',
                             fuel_type: str = '91_unleaded',
                             time_of_day: str = 'midday',
                             include_parking: bool = False,
                             parking_duration_hours: float = 2.0,
                             include_tolls: bool = True,
                             route_efficiency: float = 1.0) -> Dict:
        """
        Calculate total driving cost for a journey in Auckland
        """
        distance_km = self.calculate_distance(start_coords, end_coords)
        time_estimate = self.estimate_travel_time(distance_km, time_of_day, route_efficiency)
        fuel_calc = self.calculate_fuel_cost(distance_km, vehicle_type, fuel_type)

        time_cost = time_estimate['travel_time_hours'] * self.auckland_costs['hourly_wage']

        operating_costs = (
            distance_km * self.auckland_costs['vehicle_depreciation'] +
            distance_km * self.auckland_costs['maintenance_cost'] +
            distance_km * self.auckland_costs['insurance_cost'] +
            distance_km * self.auckland_costs['registration_cost']
        )
        
        # Calculate parking cost
        parking_cost = 0
        if include_parking:
            cbd_center = (-36.8485, 174.7633)
            cbd_distance = self.calculate_distance(end_coords, cbd_center)
            
            if cbd_distance <= 3.0:
                parking_rate = self.auckland_costs['parking_downtown']
            else:
                parking_rate = self.auckland_costs['parking_suburban']
            
            parking_cost = parking_rate * parking_duration_hours

        toll_cost = 0
        if include_tolls:
            toll_cost = self.estimate_toll_costs(start_coords, end_coords)

        total_cost = (
            fuel_calc['fuel_cost'] +
            time_cost +
            operating_costs +
            parking_cost +
            toll_cost
        )

        cost_per_km = total_cost / distance_km if distance_km > 0 else 0
        
        return {
            'distance_km': round(distance_km, 2),
            'travel_time_minutes': time_estimate['travel_time_minutes'],
            'travel_time_hours': time_estimate['travel_time_hours'],
            'average_speed_kmh': time_estimate['average_speed_kmh'],

            'fuel_cost': fuel_calc['fuel_cost'],
            'time_cost': round(time_cost, 2),
            'operating_costs': round(operating_costs, 2),
            'parking_cost': round(parking_cost, 2),
            'toll_cost': round(toll_cost, 2),

            'total_cost': round(total_cost, 2),
            'cost_per_km': round(cost_per_km, 2),

            'vehicle_type': vehicle_type,
            'fuel_type': fuel_type,
            'time_of_day': time_of_day,
            'fuel_used_liters': fuel_calc['fuel_used_liters'],
            'kwh_used': fuel_calc['kwh_used']
        }
    
    def estimate_toll_costs(self, start_coords: Tuple[float, float],
                          end_coords: Tuple[float, float]) -> float:
        """
        Estimate toll costs for a route in Auckland
        """
        toll_cost = 0

        northern_gateway_bounds = {
            'min_lat': -36.9, 'max_lat': -36.6,
            'min_lon': 174.4, 'max_lon': 174.8
        }
        
        start_lat, start_lon = start_coords
        end_lat, end_lon = end_coords
        
        if start_in_toll = (northern_gateway_bounds['min_lat'] <= start_lat <= northern_gateway_bounds['max_lat'] and
            northern_gateway_bounds['min_lon'] <= start_lon <= northern_gateway_bounds['max_lon']):
        end_in_toll = (northern_gateway_bounds['min_lat'] <= end_lat <= northern_gateway_bounds['max_lat'] and
            toll_cost += self.toll_roads['northern_gateway']

        return toll_cost
    
    def compare_vehicles(self,
                        start_coords: Tuple[float, float],
                        end_coords: Tuple[float, float],
                        time_of_day: str = 'midday') -> Dict:
        """
        Compare costs across different vehicle types
        """
        vehicles = [
            ('small_car', '91_unleaded'),
            ('medium_car', '91_unleaded'),
            ('suv', '91_unleaded'),
            ('ev_medium', 'ev_charging')
        ]
        
        comparisons = []
        
        for vehicle_type, fuel_type in vehicles:
            try:
                cost = self.calculate_driving_cost(
                    start_coords, end_coords, vehicle_type, 
                    fuel_type, time_of_day, include_parking=False
                )
                
                comparisons.append({
                    'vehicle_type': vehicle_type,
                    'fuel_type': fuel_type,
                    'total_cost': cost['total_cost'],
                    'cost_per_km': cost['cost_per_km'],
                    'travel_time_minutes': cost['travel_time_minutes'],
                    'fuel_cost': cost['fuel_cost'],
                    'operating_costs': cost['operating_costs']
                })
            except Exception as e:
                print(f"Error calculating cost for {vehicle_type}: {e}")
        
        comparisons.sort(key=lambda x: x['total_cost'])
        
        return {
            'optimal_vehicle': comparisons[0] if comparisons else None,
            'all_vehicles': comparisons,
            'distance_km': comparisons[0]['total_cost'] / comparisons[0]['cost_per_km'] if comparisons else 0
        }

cost_calculator = AucklandDrivingCostCalculator()
def calculate_driving_cost(start_coords: Tuple[float, float],
                           end_coords: Tuple[float, float],
                           vehicle_type: str = 'medium_car',
                           fuel_type: str = '91_unleaded',
                           time_of_day: str = 'midday',
                           include_parking: bool = False,
                           parking_duration_hours: float = 2.0,
                           include_tolls: bool = True,
                           route_efficiency: float = 1.0) -> Dict:
    return cost_calculator.calculate_driving_cost(
        start_coords, end_coords, vehicle_type, fuel_type,
        time_of_day, include_parking, parking_duration_hours,
        include_tolls, route_efficiency
    )
def compare_vehicles(start_coords: Tuple[float, float],
                     end_coords: Tuple[float, float],
                     time_of_day: str = 'midday') -> Dict:
    return cost_calculator.compare_vehicles(
        start_coords, end_coords, time_of_day
    )
