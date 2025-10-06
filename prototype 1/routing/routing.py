import osmnx as ox
import networkx as nx

# Load OSM graph directly (SQLite is just storage)
G = ox.graph_from_place("Auckland, New Zealand", network_type="drive")

def get_route(origin, destination):
    """Return shortest path and distance in km."""
    orig_node = ox.distance.nearest_nodes(G, origin[1], origin[0])
    dest_node = ox.distance.nearest_nodes(G, destination[1], destination[0])
    path = nx.shortest_path(G, orig_node, dest_node, weight="length")

    edges = ox.utils_graph.get_route_edge_attributes(G, path, "length")
    distance_km = sum(edges) / 1000.0
    return path, distance_km
