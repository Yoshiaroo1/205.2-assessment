import osmnx as ox
import networkx as nx
import folium
from shapely.geometry import LineString, Point
from statistics import mode

def generate_route(start_address, end_address, mode='walk'):
    """
    generates a route between two addresses in Auckland using OSM data

    Args:
        start_address (str): The starting address.
        end_address (str): The destination address.
        mode (str): The mode of transportation ('walk', 'bike', 'drive').

    Returns:
        dict: contains start, end, and HTML map of the route.
    
    """

    network_type = "walk" if mode == "pedestrian" else "drive"

    #download the street network data for Auckland
    G = ox.graph_from_place("Auckland, New Zealand", network_type=network_type)

    #geocode the start and end addresses to get their coordinates
    start_point = ox.geocode(start_address + ", Auckland, New Zealand")
    end_point = ox.geocode(end_address + ", Auckland, New Zealand")

    orig_point = ox.geocode(start_address)
    dest_point = ox.geocode(end_address)

    #find the nearest nodes in the graph to the start and end points
    orig_node = ox.distance.nearest_nodes(G, start_point[1], start_point[0])
    dest_node = ox.distance.nearest_nodes(G, end_point[1], end_point[0])

    #compute the shortest path between the origin and destination nodes
    route = nx.shortest_path(G, orig_node, dest_node, weight='length')

    #create a folium map centered around the start point
    m = ox.plot_route_folium(G, route, route_color='blue', weight=5, opacity=0.7, zoom=14, tiles='OpenStreetMap')

    return {
        "start": start_address,
        "end": end_address,
        "map": m._repr_html_()
    }




