"""Test data constants for location ingestion tests.

Provides predefined coordinates, H3 cells, and expected geography data
for consistent testing across unit and integration tests.
"""

import h3

# San Francisco, California, USA
SAN_FRANCISCO = {
    "latitude": 37.7749,
    "longitude": -122.4194,
    "h3_res8": h3.latlng_to_cell(37.7749, -122.4194, 8),
    "h3_res6": h3.latlng_to_cell(37.7749, -122.4194, 6),
    "country": "United States",
    "country_iso2": "US",
    "state": "California",
    "state_code": "CA",
}

# Tokyo, Japan
TOKYO = {
    "latitude": 35.6895,
    "longitude": 139.6917,
    "h3_res8": h3.latlng_to_cell(35.6895, 139.6917, 8),
    "h3_res6": h3.latlng_to_cell(35.6895, 139.6917, 6),
    "country": "Japan",
    "country_iso2": "JP",
    "state": "Tokyo",
    "state_code": "13",
}

# Paris, France
PARIS = {
    "latitude": 48.8566,
    "longitude": 2.3522,
    "h3_res8": h3.latlng_to_cell(48.8566, 2.3522, 8),
    "h3_res6": h3.latlng_to_cell(48.8566, 2.3522, 6),
    "country": "France",
    "country_iso2": "FR",
    "state": "Île-de-France",
    "state_code": "IDF",
}

# International waters (Atlantic Ocean)
INTERNATIONAL_WATERS = {
    "latitude": 0.0,
    "longitude": -30.0,
    "h3_res8": h3.latlng_to_cell(0.0, -30.0, 8),
    "h3_res6": h3.latlng_to_cell(0.0, -30.0, 6),
    "country": None,
    "country_iso2": None,
    "state": None,
    "state_code": None,
}

# North Pole
NORTH_POLE = {
    "latitude": 89.9999,  # Can't use exactly 90.0 due to H3 limitations
    "longitude": 0.0,
    "h3_res8": h3.latlng_to_cell(89.9999, 0.0, 8),
    "h3_res6": h3.latlng_to_cell(89.9999, 0.0, 6),
    "country": None,
    "country_iso2": None,
    "state": None,
    "state_code": None,
}

# Los Angeles, California, USA (same state as SF)
LOS_ANGELES = {
    "latitude": 34.0522,
    "longitude": -118.2437,
    "h3_res8": h3.latlng_to_cell(34.0522, -118.2437, 8),
    "h3_res6": h3.latlng_to_cell(34.0522, -118.2437, 6),
    "country": "United States",
    "country_iso2": "US",
    "state": "California",
    "state_code": "CA",
}

# New York, USA (different state, same country as SF)
NEW_YORK = {
    "latitude": 40.7128,
    "longitude": -74.0060,
    "h3_res8": h3.latlng_to_cell(40.7128, -74.0060, 8),
    "h3_res6": h3.latlng_to_cell(40.7128, -74.0060, 6),
    "country": "United States",
    "country_iso2": "US",
    "state": "New York",
    "state_code": "NY",
}

# Monaco (very small country, often fits in single H3 cell)
MONACO = {
    "latitude": 43.7384,
    "longitude": 7.4246,
    "h3_res8": h3.latlng_to_cell(43.7384, 7.4246, 8),
    "h3_res6": h3.latlng_to_cell(43.7384, 7.4246, 6),
    "country": "Monaco",
    "country_iso2": "MC",
    "state": None,
    "state_code": None,
}

# Sydney, Australia
SYDNEY = {
    "latitude": -33.8688,
    "longitude": 151.2093,
    "h3_res8": h3.latlng_to_cell(-33.8688, 151.2093, 8),
    "h3_res6": h3.latlng_to_cell(-33.8688, 151.2093, 6),
    "country": "Australia",
    "country_iso2": "AU",
    "state": "New South Wales",
    "state_code": "NSW",
}

# Antimeridian crossing (near date line)
ANTIMERIDIAN = {
    "latitude": 0.0,
    "longitude": 179.9,
    "h3_res8": h3.latlng_to_cell(0.0, 179.9, 8),
    "h3_res6": h3.latlng_to_cell(0.0, 179.9, 6),
    "country": None,
    "country_iso2": None,
    "state": None,
    "state_code": None,
}

# All test locations for easy iteration
ALL_LOCATIONS = [
    SAN_FRANCISCO,
    TOKYO,
    PARIS,
    INTERNATIONAL_WATERS,
    NORTH_POLE,
    LOS_ANGELES,
    NEW_YORK,
    MONACO,
    SYDNEY,
    ANTIMERIDIAN,
]

# Locations with valid geography (not international waters/poles)
LAND_LOCATIONS = [
    SAN_FRANCISCO,
    TOKYO,
    PARIS,
    LOS_ANGELES,
    NEW_YORK,
    MONACO,
    SYDNEY,
]

# Locations without geography
WATER_LOCATIONS = [
    INTERNATIONAL_WATERS,
    NORTH_POLE,
    ANTIMERIDIAN,
]
