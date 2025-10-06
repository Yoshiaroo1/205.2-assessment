from flask import Flask, render_template, request
import osmnx as ox
import folium
from shapely.geometry import LineString

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        origin = request.form["origin"]
        destination = request.form["destination"]

        try:
            #Geocode input addresses
            orig_point = ox.geocode(origin)
            dest_point = ox.geocode(destination)

            #Build drivable graph around area
            place_name = "Auckland, New Zealand"
            G = ox.graph_from_place(place_name, network_type="drive")

            #Find nearest graph nodes
            orig_node = ox.distance.nearest_nodes(G, orig_point[1], orig_point[0])
            dest_node = ox.distance.nearest_nodes(G, dest_point[1], dest_point[0])

            #Shortest path
            route = ox.shortest_path(G, orig_node, dest_node, weight="length")

            #Create Folium map centered between origin/destination
            mid_lat = (orig_point[0] + dest_point[0]) / 2
            mid_lon = (orig_point[1] + dest_point[1]) / 2
            m = folium.Map(location=[mid_lat, mid_lon], zoom_start=12)

            #Get route coordinates and plot line
            route_coords = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in route]
            folium.PolyLine(route_coords, color="blue", weight=5, opacity=0.7).add_to(m)

            #Add markers
            folium.Marker(location=orig_point, popup="Origin", icon=folium.Icon(color="green")).add_to(m)
            folium.Marker(location=dest_point, popup="Destination", icon=folium.Icon(color="red")).add_to(m)

            #Save map to file
            map_path = "static/route_map.html"
            m.save(map_path)

            return render_template("result.html",
                       origin=origin,
                       destination=destination,
                       route_map="static/route_map.html")


        except Exception as e:
            return render_template("index.html", error=str(e))

    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
