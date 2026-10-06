from rest_framework.views import APIView
from rest_framework.response import Response
from .utils import geocode_location, get_route, calculate_optimal_fuel_stops

class RoutePlannerView(APIView):
    def get(self, request):
        # 1. Grab start and finish from the URL
        start_loc = request.query_params.get('start')
        finish_loc = request.query_params.get('finish')
        
        if not start_loc or not finish_loc:
            return Response({"error": "Please provide both 'start' and 'finish' parameters (e.g. ?start=Chicago,IL&finish=Dallas,TX)"}, status=400)
            
        # 2. Geocode both locations (API Calls #1 and #2)
        start_coords = geocode_location(start_loc)
        finish_coords = geocode_location(finish_loc)
        
        if not start_coords[0] or not finish_coords[0]:
            return Response({"error": "Could not find coordinates for the provided locations."}, status=400)
            
        # 3. Get the route distance and map geometry from OSRM (API Call #3)
        total_distance, map_geometry = get_route(start_coords, finish_coords)
        
        if not total_distance:
            return Response({"error": "Could not calculate a route between these locations."}, status=400)
            
        # 4. Run our blazing fast in-memory math algorithm
        fuel_stops, total_cost = calculate_optimal_fuel_stops(start_coords, finish_coords, total_distance, map_geometry)
        
        if isinstance(fuel_stops, dict) and "error" in fuel_stops:
            return Response(fuel_stops, status=400)
        
        # 5. Return the JSON payload
        return Response({
            "route_summary": {
                "start": start_loc,
                "finish": finish_loc,
                "total_distance_miles": round(total_distance, 2),
                "total_fuel_cost": f"${total_cost}"
            },
            "fuel_stops": fuel_stops,
            "map_geojson": map_geometry
        })