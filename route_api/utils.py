import requests
import json
import math
import os
from functools import lru_cache # <--- 1. Import this

# --- SPEED HACK: Load data into RAM once when Django starts ---
STATIONS_CACHE = []
json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'geocoded_stations.json')

try:
    with open(json_path, 'r') as f:
        STATIONS_CACHE = json.load(f)
except FileNotFoundError:
    print("WARNING: geocoded_stations.json not found. Run preprocessing script.")

def get_straight_line_distance(lat1, lon1, lat2, lon2):
    R = 3958.8 
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# --- 2. Add the cache decorator here ---
@lru_cache(maxsize=1000)
def geocode_location(location_str):
    url = f"https://nominatim.openstreetmap.org/search?q={location_str}&format=json&limit=1"
    headers = {'User-Agent': 'SpotterAssessmentApp/1.0'}
    response = requests.get(url, headers=headers).json()
    if response:
        return float(response[0]['lat']), float(response[0]['lon'])
    return None, None

#  the cache decorator 
@lru_cache(maxsize=500)
def get_route(start_coords, finish_coords):
    url = f"http://router.project-osrm.org/route/v1/driving/{start_coords[1]},{start_coords[0]};{finish_coords[1]},{finish_coords[0]}?geometries=geojson&overview=full"
    response = requests.get(url).json()
    
    if response.get('code') != 'Ok':
        return None, None
        
    route_data = response['routes'][0]
    distance_miles = route_data['distance'] * 0.000621371
    # Note: Tuples are used internally for cache hashing
    map_geometry = route_data['geometry'] 
    
    return distance_miles, map_geometry


# --- MAIN ALGORITHM ---
def calculate_optimal_fuel_stops(start_coords, finish_coords, total_route_distance, map_geometry):
    if not STATIONS_CACHE:
        return {"error": "Station data not loaded."}, 0

    MAX_RANGE = 500
    MPG = 10
    
    # 1. Create a bounding box to instantly filter out 90% of stations we don't need
    min_lat, max_lat = min(start_coords[0], finish_coords[0]) - 2, max(start_coords[0], finish_coords[0]) + 2
    min_lon, max_lon = min(start_coords[1], finish_coords[1]) - 2, max(start_coords[1], finish_coords[1]) + 2
    
    route_coords = map_geometry['coordinates']
    route_points = []
    cum_dist = 0.0
    
    for i in range(len(route_coords)):
        lon, lat = route_coords[i]
        if i > 0:
            prev_lon, prev_lat = route_coords[i-1]
            cum_dist += get_straight_line_distance(prev_lat, prev_lon, lat, lon)
        route_points.append({'lat': lat, 'lon': lon, 'mile': cum_dist})
        
    scale_factor = total_route_distance / cum_dist if cum_dist > 0 else 1
    for pt in route_points:
        pt['mile'] *= scale_factor
        
    # Downsample points for blazing fast performance while maintaining good accuracy
    fast_route_points = route_points[::10]
        
    valid_stations = []
    for s in STATIONS_CACHE:
        if s.get('lat') and s.get('lon'):
            if min_lat <= s['lat'] <= max_lat and min_lon <= s['lon'] <= max_lon:
                min_dist_to_route = float('inf')
                route_mile_marker = 0
                
                for pt in fast_route_points:
                    if abs(s['lat'] - pt['lat']) < 0.5 and abs(s['lon'] - pt['lon']) < 0.5:
                        dist = get_straight_line_distance(pt['lat'], pt['lon'], s['lat'], s['lon'])
                        if dist < min_dist_to_route:
                            min_dist_to_route = dist
                            route_mile_marker = pt['mile']
                            
                if min_dist_to_route <= 10.0:
                    s_copy = s.copy()
                    s_copy['mile_marker'] = route_mile_marker
                    valid_stations.append(s_copy)
                
    # Sort stations geographically from start to finish
    valid_stations.sort(key=lambda x: x['mile_marker'])
    
    stops = []
    total_cost = 0.0
    current_mile = 0
    
    # 2. Greedy Algorithm: Jump 500 miles, find cheapest gas, repeat
    while current_mile + MAX_RANGE < total_route_distance:
        reachable = [s for s in valid_stations if current_mile < s['mile_marker'] <= current_mile + MAX_RANGE]
        
        if not reachable:
            break # Vehicle cannot make it, gap is too large
            
        # Find absolute cheapest station in range
        best_station = min(reachable, key=lambda x: x['price'])
        
        miles_driven = best_station['mile_marker'] - current_mile
        gallons_needed = miles_driven / MPG
        cost = gallons_needed * best_station['price']
        
        total_cost += cost
        stops.append({
            "station_name": best_station['name'],
            "location": f"{best_station['city']}, {best_station['state']}",
            "price_per_gallon": best_station['price'],
            "gallons_purchased": round(gallons_needed, 2),
            "cost_for_stop": round(cost, 2),
            "coordinates": {"lat": best_station['lat'], "lon": best_station['lon']}
        })
        
        current_mile = best_station['mile_marker']
        
    # 3. Final stretch to the finish line
    if current_mile + MAX_RANGE < total_route_distance:
        return {"error": "No fuel stations in range to complete the route."}, 0

    distance_to_finish = total_route_distance - current_mile
    if distance_to_finish > 0 and stops:
        extra_gallons = distance_to_finish / MPG
        last_stop = stops[-1]
        extra_cost = extra_gallons * last_stop['price_per_gallon']
        
        last_stop['gallons_purchased'] = round(last_stop['gallons_purchased'] + extra_gallons, 2)
        last_stop['cost_for_stop'] = round(last_stop['cost_for_stop'] + extra_cost, 2)
        total_cost += extra_cost

    return stops, round(total_cost, 2)