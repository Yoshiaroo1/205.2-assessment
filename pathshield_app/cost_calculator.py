import geopandas as gpd
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional

class AucklandTransportCostCalculator:
    """
    Cost calculator for public transport in Auckland, NZ
    Uses AT HOP card pricing structure and fare rules
    """
    
    def __init__(self, gtfs_data_path: str = "cleaned_output"):
        """
        Initialize the cost calculator with GTFS data
        
        Args:
            gtfs_data_path: Path to cleaned GTFS data
        """

        self.stops = gpd.read_file(f"{gtfs_data_path}/cleaned_stops.gpkg")
        self.routes = gpd.read_file(f"{gtfs_data_path}/cleaned_shapes.gpkg")

        try:
            self.fare_attributes = pd.read_csv(f"{gtfs_data_path}/../geotagged_output/gtfs_agency.csv")
            self.fare_rules = pd.read_csv(f"{gtfs_data_path}/../geotagged_output/gtfs_routes.csv")
        except:
            print("Warning: Could not load fare data, using default pricing")
            self.fare_attributes = None
            self.fare_rules = None

        self.fare_structure = {
            'adult': {
                'base_fare': 1.0,
                'per_km': 0.25,
                'max_daily': 20.0,
                'transfer_discount': 0.5
            },
            'child': {
                'base_fare': 0.5,
                'per_km': 0.12,
                'max_daily': 10.0,
                'transfer_discount': 0.5
            },
            'student': {
                'base_fare': 0.75,
                'per_km': 0.18,
                'max_daily': 15.0,
                'transfer_discount': 0.5
            }
        }

        self.service_multipliers = {
            'bus': 1.0,
            'train': 1.2,
            'ferry': 1.5,
            'light_rail': 1.1
        }

        self.zones = self._calculate_zones()
        
    def _calculate_zones(self) -> gpd.GeoDataFrame:
        """
        Calculate fare zones based on distance from CBD
        Returns a GeoDataFrame with zone boundaries
        """
        auckland_cbd = (174.7633, -36.8485)

        stops_copy = self.stops.copy()
        stops_copy['distance_from_cbd'] = stops_copy.apply(
            lambda row: self._calculate_distance(
                auckland_cbd[0], auckland_cbd[1], 
                row['stop_lon'], row['stop_lat']
            ), axis=1
        )

        stops_copy['zone'] = pd.cut(
            stops_copy['distance_from_cbd'],
            bins=[0, 5, 10, 20, 50, float('inf')],
            labels=['Zone 1', 'Zone 2', 'Zone 3', 'Zone 4', 'Zone 5']
        )
        
        return stops_copy[['stop_id', 'zone', 'distance_from_cbd']]
    
    def _calculate_distance(self, lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """
        Calculate great-circle distance between two points in kilometers
        """
        R = 6371
        
        dlat = np.radians(lat2 - lat1)
        dlon = np.radians(lon2 - lon1)
        
        a = (np.sin(dlat/2) * np.sin(dlat/2) + 
             np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * 
             np.sin(dlon/2) * np.sin(dlon/2))
        
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
        return R * c
    
    def calculate_route_cost(self, 
                           start_stop_id: str, 
                           end_stop_id: str, 
                           passenger_type: str = 'adult',
                           service_type: str = 'bus',
                           transfers: int = 0,
                           time_of_day: str = 'peak') -> Dict:
        """
        Calculate the cost for a single journey
        
        Args:
            start_stop_id: Starting stop ID
            end_stop_id: Ending stop ID
            passenger_type: 'adult', 'child', or 'student'
            service_type: 'bus', 'train', 'ferry', 'light_rail'
            transfers: Number of transfers
            time_of_day: 'peak' or 'off_peak'
            
        Returns:
            Dictionary with cost breakdown
        """
        if passenger_type not in self.fare_structure:
            raise ValueError(f"Invalid passenger type: {passenger_type}")
        
        if service_type not in self.service_multipliers:
            raise ValueError(f"Invalid service type: {service_type}")
        
        start_stop = self.stops[self.stops['stop_id'] == start_stop_id]
        end_stop = self.stops[self.stops['stop_id'] == end_stop_id]
        
        if len(start_stop) == 0 or len(end_stop) == 0:
            raise ValueError("Invalid stop IDs provided")
        
        start_coords = (start_stop.iloc[0]['stop_lon'], start_stop.iloc[0]['stop_lat'])
        end_coords = (end_stop.iloc[0]['stop_lon'], end_stop.iloc[0]['stop_lat'])

        distance_km = self._calculate_distance(
            start_coords[0], start_coords[1],
            end_coords[0], end_coords[1]
        )

        fare_rules = self.fare_structure[passenger_type]
        service_multiplier = self.service_multipliers[service_type]

        time_multiplier = 1.0 if time_of_day == 'off_peak' else 1.1

        base_cost = fare_rules['base_fare']
        distance_cost = distance_km * fare_rules['per_km']

        service_cost = (base_cost + distance_cost) * service_multiplier

        time_adjusted_cost = service_cost * time_multiplier

        transfer_discount = fare_rules['transfer_discount'] * transfers
        final_cost = max(time_adjusted_cost - transfer_discount, base_cost)

        capped_cost = min(final_cost, fare_rules['max_daily'])
        
        return {
            'base_fare': base_cost,
            'distance_km': distance_km,
            'distance_cost': distance_cost,
            'service_multiplier': service_multiplier,
            'time_multiplier': time_multiplier,
            'transfer_discount': transfer_discount,
            'final_cost': round(capped_cost, 2),
            'service_type': service_type,
            'passenger_type': passenger_type
        }
    
    def calculate_multi_leg_journey(self, 
                                  journey_legs: List[Tuple[str, str, str]], 
                                  passenger_type: str = 'adult',
                                  time_of_day: str = 'peak') -> Dict:
        """
        Calculate cost for a journey with multiple legs/transfers
        
        Args:
            journey_legs: List of (start_stop, end_stop, service_type) tuples
            passenger_type: Type of passenger
            time_of_day: 'peak' or 'off_peak'
            
        Returns:
            Dictionary with total cost and breakdown
        """
        total_cost = 0
        leg_breakdown = []
        
        for i, (start_stop, end_stop, service_type) in enumerate(journey_legs):
            transfers = max(0, i)
            
            leg_cost = self.calculate_route_cost(
                start_stop, end_stop, passenger_type, 
                service_type, transfers, time_of_day
            )
            
            total_cost += leg_cost['final_cost']
            leg_breakdown.append({
                'leg': i + 1,
                'start_stop': start_stop,
                'end_stop': end_stop,
                'service_type': service_type,
                'cost': leg_cost['final_cost'],
                'distance_km': leg_cost['distance_km']
            })

        daily_cap = self.fare_structure[passenger_type]['max_daily']
        final_total_cost = min(total_cost, daily_cap)
        
        return {
            'total_cost': round(final_total_cost, 2),
            'daily_cap_applied': final_total_cost < total_cost,
            'leg_breakdown': leg_breakdown,
            'number_of_legs': len(journey_legs),
            'passenger_type': passenger_type
        }
    
    def optimize_route_cost(self, 
                          start_stop_id: str, 
                          end_stop_id: str,
                          passenger_type: str = 'adult',
                          max_transfers: int = 2) -> Dict:
        """
        Find the most cost-effective route between two stops
        
        Args:
            start_stop_id: Starting stop ID
            end_stop_id: Ending stop ID
            passenger_type: Type of passenger
            max_transfers: Maximum allowed transfers
            
        Returns:
            Dictionary with optimal route and cost
        """

        service_types = ['bus', 'train']
        results = []
        
        for service_type in service_types:
            try:
                cost = self.calculate_route_cost(
                    start_stop_id, end_stop_id, 
                    passenger_type, service_type
                )
                results.append({
                    'service_type': service_type,
                    'cost': cost['final_cost'],
                    'distance_km': cost['distance_km']
                })
            except Exception as e:
                print(f"Could not calculate cost for {service_type}: {e}")

        results.sort(key=lambda x: x['cost'])
        
        return {
            'optimal_route': results[0] if results else None,
            'all_options': results,
            'start_stop': start_stop_id,
            'end_stop': end_stop_id
        }
    
    def get_stop_suggestions(self, query: str) -> List[Dict]:
        """
        Find stops matching a search query
        
        Args:
            query: Search string (stop name or code)
            
        Returns:
            List of matching stops
        """
        matches = self.stops[
            self.stops['stop_name'].str.contains(query, case=False, na=False) |
            self.stops['stop_code'].str.contains(query, case=False, na=False)
        ]
        
        return matches[['stop_id', 'stop_name', 'stop_code', 'stop_lat', 'stop_lon']].to_dict('records')

if __name__ == "__main__":

    calculator = AucklandTransportCostCalculator()
    
    print("Auckland Transport Cost Calculator")
    print("=" * 50)

    print("\n1. Simple Bus Journey:")
    cost = calculator.calculate_route_cost(
        start_stop_id="your_start_stop_id",
        end_stop_id="your_end_stop_id",
        passenger_type="adult",
        service_type="bus"
    )
    print(f"Cost: NZ${cost['final_cost']}")
    print(f"Distance: {cost['distance_km']:.1f} km")

    print("\n2. Multi-leg Journey (Bus + Train):")
    journey_legs = [
        ("stop1", "stop2", "bus"),
        ("stop2", "stop3", "train")
    ]
    multi_cost = calculator.calculate_multi_leg_journey(journey_legs)
    print(f"Total Cost: NZ${multi_cost['total_cost']}")

    print("\n3. Route Cost Optimization:")
    optimization = calculator.optimize_route_cost("stop1", "stop3")
    print(f"Optimal service: {optimization['optimal_route']['service_type']}")
    print(f"Optimal cost: NZ${optimization['optimal_route']['cost']}")