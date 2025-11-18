import numpy as np
from model import ETAModel
from cost_calculator import AucklandDrivingCostCalculator

class EnhancedETAModel:
    """
    Enhanced model that combines ETA prediction with cost calculation
    while preserving the original ETAModel functionality
    """
    
    def __init__(self):
        self.eta_model = ETAModel()
        self.cost_calculator = AucklandDrivingCostCalculator()
    
    def train(self, X, y):
        """Train the underlying ETA model"""
        self.eta_model.train(X, y)
    
    def predict(self, distance, hour, day):
        """Original ETA prediction functionality"""
        return self.eta_model.predict(distance, hour, day)
    
    def predict_comprehensive(self, start_coords, end_coords, hour, day, 
                            vehicle_type='medium_car', fuel_type='91_unleaded',
                            **kwargs):
        """
        Comprehensive prediction including both ETA and cost analysis
        """
        # Calculate distance
        distance_km = self.cost_calculator.calculate_distance(start_coords, end_coords)
        
        # Get ML-predicted travel time
        ml_travel_time = self.eta_model.predict(distance_km, hour, day)
        
        # Convert hour to time category
        time_of_day = self._convert_hour_to_time_category(hour)
        
        # Calculate cost analysis
        cost_analysis = self.cost_calculator.calculate_driving_cost(
            start_coords=start_coords,
            end_coords=end_coords,
            vehicle_type=vehicle_type,
            fuel_type=fuel_type,
            time_of_day=time_of_day,
            **kwargs
        )
        
        # Combine results
        comprehensive_result = {
            'eta_prediction': {
                'travel_time_minutes': round(ml_travel_time, 2),
                'travel_time_hours': round(ml_travel_time / 60, 2),
                'distance_km': round(distance_km, 2),
                'prediction_method': 'ml_model' if self.eta_model.trained else 'fallback'
            },
            'cost_analysis': cost_analysis,
            'summary': {
                'total_travel_time_minutes': round(ml_travel_time, 2),
                'total_cost_nzd': cost_analysis['total_cost'],
                'cost_per_km': cost_analysis['cost_per_km'],
                'vehicle_type': vehicle_type,
                'time_of_day': time_of_day
            }
        }
        
        return comprehensive_result
    
    def _convert_hour_to_time_category(self, hour):
        """Convert hour (0-23) to time_of_day category"""
        if 4 <= hour < 6:
            return 'early_morning'
        elif 6 <= hour < 9:
            return 'morning_peak'
        elif 9 <= hour < 15:
            return 'midday'
        elif 15 <= hour < 18:
            return 'afternoon_peak'
        elif 18 <= hour < 22:
            return 'evening'
        else:
            return 'late_night'