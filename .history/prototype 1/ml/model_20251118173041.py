import numpy as np
import xgboost as xgb
from cost_calculator import AucklandDrivingCostCalculator

class ETAModel:
    def __init__(self):
        self.model = xgb.XGBRegressor()
        self.cost_calculator = AucklandDrivingCostCalculator()
        self.trained = False

    def train(self, X, y):
        self.model.fit(X, y)
        self.trained = True

    def predict(self, distance, hour, day):
        """Predict travel time in minutes (original functionality)"""
        if not self.trained:
            # fallback = 40 km/h average speed
            return (distance / 40) * 60
        X = np.array([[distance, hour, day]])
        return float(self.model.predict(X)[0])

    def predict_with_cost(self, start_coords, end_coords, hour, day, 
                         vehicle_type='medium_car', fuel_type='91_unleaded',
                         include_parking=False, parking_duration_hours=2.0,
                         include_tolls=True):
        """
        Enhanced prediction that returns both ETA and cost analysis
        """
        # Convert hour to time_of_day category
        time_of_day = self._convert_hour_to_time_category(hour)
        
        # Calculate distance
        distance_km = self.cost_calculator.calculate_distance(start_coords, end_coords)
        
        # Predict travel time using the ML model
        if self.trained:
            travel_time_minutes = self.predict(distance_km, hour, day)
        else:
            # Fallback to cost calculator's time estimation
            time_estimate = self.cost_calculator.estimate_travel_time(
                distance_km, time_of_day
            )
            travel_time_minutes = time_estimate['travel_time_minutes']
        
        # Calculate comprehensive cost analysis
        cost_analysis = self.cost_calculator.calculate_driving_cost(
            start_coords=start_coords,
            end_coords=end_coords,
            vehicle_type=vehicle_type,
            fuel_type=fuel_type,
            time_of_day=time_of_day,
            include_parking=include_parking,
            parking_duration_hours=parking_duration_hours,
            include_tolls=include_tolls
        )
        
        # Add the ML-predicted travel time to the cost analysis
        cost_analysis['ml_predicted_travel_time_minutes'] = round(travel_time_minutes, 2)
        cost_analysis['ml_predicted_travel_time_hours'] = round(travel_time_minutes / 60, 2)
        
        return cost_analysis

    def compare_vehicles_with_ml(self, start_coords, end_coords, hour, day):
        """
        Compare different vehicle types using ML-predicted travel times
        """
        time_of_day = self._convert_hour_to_time_category(hour)
        distance_km = self.cost_calculator.calculate_distance(start_coords, end_coords)
        
        # Get ML-predicted travel time
        if self.trained:
            ml_travel_time = self.predict(distance_km, hour, day)
        else:
            time_estimate = self.cost_calculator.estimate_travel_time(distance_km, time_of_day)
            ml_travel_time = time_estimate['travel_time_minutes']
        
        # Get vehicle comparisons
        vehicle_comparison = self.cost_calculator.compare_vehicles(
            start_coords, end_coords, time_of_day
        )
        
        # Enhance comparison with ML predictions
        for vehicle in vehicle_comparison['all_vehicles']:
            vehicle['ml_predicted_travel_time'] = ml_travel_time
        
        vehicle_comparison['ml_predicted_travel_time'] = ml_travel_time
        vehicle_comparison['distance_km'] = distance_km
        
        return vehicle_comparison

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

# Backward compatibility - maintain original functionality
def create_eta_model():
    """Factory function to create ETAModel (maintains original interface)"""
    return ETAModel()