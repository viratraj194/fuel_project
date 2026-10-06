
# Fuel Optimization Routing API

 **Loom Video Walkthrough:** [Insert Loom Link Here]

    ## Overview
    This is a Django API that calculates the most cost-effective fuel stops for a vehicle traveling between two locations in the US. It assumes a vehicle
  range of 500 miles and 10 miles-per-gallon (MPG).

    ## Quick Start

    1. Clone the repository and navigate into the project directory.
    2. Set up a virtual environment:
       ```bash
       python -m venv env
       source env/bin/activate  # On Windows use: env\Scripts\activate

  3. Install the required packages:
    pip install django requests pandas

  4. Start the local server:
    python manage.py runserver


  ## API Usage

  Endpoint: GET /api/route/

  Example Request:

    http://127.0.0.1:8000/api/route/?start=Chicago,IL&finish=Miami, FL

  ## Architecture & Design Decisions

  I focused heavily on response time and minimizing external API rate limits. Hitting an external map API on the fly to calculate distances for 8,000+ gas
  stations is too slow, so I built the following architecture:

  • Offline Data Pipeline: I wrote preprocess_data.py to batch-geocode the provided CSV against OpenStreetMap's Nominatim API. It handles rate-limiting
  and outputs a clean geocoded_stations.json.
  • In-Memory Data: When the Django server boots, it loads the JSON file directly into RAM. This drops disk I/O and database queries to zero during a live
  request.
  • Route Snapping Algorithm: The API makes exactly one call to OSRM to get the physical driving geometry. My algorithm downsamples the route points and
  mathematically "snaps" the gas stations to the actual highway, discarding any station more than 10 miles off the physical route.
  • Greedy Optimization: The logic walks along the actual route path, looking ahead up to the 500-mile maximum range. It selects the absolute cheapest
  station in that window, calculates the exact gallons needed, and repeats.
  • Lightweight Caching: To prevent spamming external APIs on repeat queries, I wrapped the network calls in Python's @lru_cache. It provides millisecond
  response times for cached routes without requiring a heavy Redis setup for this assessment.

  ## Edge Cases Handled

  • Unreachable Destinations: If a route contains a gap larger than 500 miles with zero stations in the dataset (e.g., Los Angeles to Seattle), the API
  catches the gap and gracefully returns a 400 Bad Request rather than attempting to calculate impossible math.