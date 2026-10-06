import pandas as pd
import requests
import json
import time
import os

def process_csv():
    print("Loading CSV...")
    df = pd.read_csv("fuel-prices-for-be-assessment.csv")
    df['City'] = df['City'].astype(str).str.strip()
    df['State'] = df['State'].astype(str).str.strip()
    
    stations = []
    city_cache = {} 
    
    # 1. AUTO-RESUME: Check if we already have a partial file saved
    if os.path.exists('geocoded_stations.json'):
        try:
            with open('geocoded_stations.json', 'r') as f:
                stations = json.load(f)
                print(f"Found {len(stations)} completed stations. Resuming where we left off...")
                # Re-populate our cache so we don't repeat API calls
                for s in stations:
                    if s.get('lat') and s.get('lon'):
                        city_query = f"{s['city']}, {s['state']}, USA"
                        city_cache[city_query] = (s['lat'], s['lon'])
        except Exception:
            print("Starting fresh.")

    # Start exactly where the last run failed/stopped
    start_index = len(stations)
    
    url = "https://nominatim.openstreetmap.org/search"
    headers = {'User-Agent': 'SpotterAssessmentApp_123/1.0'}
    
    print(f"Starting at row {start_index}...")
    
    for index in range(start_index, len(df)):
        row = df.iloc[index]
        city_query = f"{row['City']}, {row['State']}, USA"
        lat, lon = None, None
        
        if city_query in city_cache:
            lat, lon = city_cache[city_query]
            print(f"[{index}/8151] CACHE MATCH: {city_query}")
        else:
            params = {'q': city_query, 'format': 'json', 'limit': 1}
            try:
                # 2. TIMEOUT LIMIT: If the server hangs for 5 seconds, move on!
                response = requests.get(url, params=params, headers=headers, timeout=5)
                data = response.json()
                
                if data:
                    lat = float(data[0]['lat'])
                    lon = float(data[0]['lon'])
                    city_cache[city_query] = (lat, lon)
                    print(f"[{index}/8151] API SUCCESS: {city_query}")
                else:
                    print(f"[{index}/8151] NOT FOUND: {city_query}")
                    
            except Exception as e:
                # If it times out or errors, we just skip it and try the next one
                print(f"[{index}/8151] TIMEOUT/ERROR: Moving past {city_query}")
                
            # Respect the API limit
            time.sleep(1.1)

        stations.append({
            "name": row['Truckstop Name'],
            "address": row['Address'],
            "city": row['City'],
            "state": row['State'],
            "price": float(row['Retail Price']),
            "lat": lat,
            "lon": lon
        })
        
        # 3. AUTO-SAVE: Save to the hard drive every 50 stations
        if index % 50 == 0:
            with open('geocoded_stations.json', 'w') as f:
                json.dump(stations, f, indent=4)

    # Final save when it hits 8151
    with open('geocoded_stations.json', 'w') as f:
        json.dump(stations, f, indent=4)
    
    print("Done! Saved all 8151 rows to geocoded_stations.json")

if __name__ == "__main__":
    process_csv()