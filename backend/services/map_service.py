"""Map service for retrieving user's visited areas."""

import math
from typing import Optional

import h3
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import is_sqlite_session


def _haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate the great-circle distance between two points in meters."""
    R = 6371000  # Earth's radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _create_circle_polygon(center_lat: float, center_lng: float, radius_meters: float, num_points: int = 32) -> list:
    """Create a circle polygon as a list of [lng, lat] coordinates."""
    coords = []
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        # Calculate point at given angle and distance from center
        # Using approximate formula for small distances
        dlat = (radius_meters / 6371000) * math.cos(angle)
        dlng = (radius_meters / 6371000) * math.sin(angle) / math.cos(math.radians(center_lat))
        lat = center_lat + math.degrees(dlat)
        lng = center_lng + math.degrees(dlng)
        coords.append([lng, lat])
    coords.append(coords[0])  # Close the polygon
    return coords


class MapService:
    """Service for map-related queries."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self._is_sqlite = is_sqlite_session(db)

    def get_summary(self) -> dict:
        """Get all countries and regions the user has visited.

        Returns:
            dict with 'countries' and 'regions' lists
        """
        # Query distinct countries
        countries_query = text("""
            SELECT DISTINCT rc.iso2 AS code, rc.name
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            JOIN regions_country rc ON hc.country_id = rc.id
            WHERE ucv.user_id = :user_id
            ORDER BY rc.name
        """)
        countries_result = self.db.execute(
            countries_query, {"user_id": self.user_id}
        ).fetchall()

        countries = [
            {"code": row.code, "name": row.name}
            for row in countries_result
        ]

        # Query distinct regions
        # SQLite uses || for string concatenation, PostgreSQL uses CONCAT
        if self._is_sqlite:
            regions_query = text("""
                SELECT DISTINCT
                    rc.iso2 || '-' || rs.code AS code,
                    rs.name
                FROM user_cell_visits ucv
                JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
                JOIN regions_state rs ON hc.state_id = rs.id
                JOIN regions_country rc ON rs.country_id = rc.id
                WHERE ucv.user_id = :user_id
                ORDER BY rs.name
            """)
        else:
            regions_query = text("""
                SELECT DISTINCT
                    CONCAT(rc.iso2, '-', rs.code) AS code,
                    rs.name
                FROM user_cell_visits ucv
                JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
                JOIN regions_state rs ON hc.state_id = rs.id
                JOIN regions_country rc ON rs.country_id = rc.id
                WHERE ucv.user_id = :user_id
                ORDER BY rs.name
            """)
        regions_result = self.db.execute(
            regions_query, {"user_id": self.user_id}
        ).fetchall()

        regions = [
            {"code": row.code, "name": row.name}
            for row in regions_result
        ]

        return {"countries": countries, "regions": regions}

    def get_cells_in_viewport(
        self,
        min_lng: float,
        min_lat: float,
        max_lng: float,
        max_lat: float,
        limit: Optional[int] = None,
    ) -> dict:
        """Get H3 cell indexes within the bounding box.

        Args:
            min_lng: Western longitude bound
            min_lat: Southern latitude bound
            max_lng: Eastern longitude bound
            max_lat: Northern latitude bound
            limit: Optional maximum number of cells to return (for future use)

        Returns:
            dict with 'res6' and 'res8' lists of H3 index strings
        """
        # SQLite doesn't have PostGIS, so we return all cells and filter client-side
        if self._is_sqlite:
            query = text("""
                SELECT hc.h3_index, hc.res
                FROM user_cell_visits ucv
                JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
                WHERE ucv.user_id = :user_id
                  AND hc.res IN (6, 8)
                ORDER BY hc.h3_index
            """)
            result = self.db.execute(query, {"user_id": self.user_id}).fetchall()
        else:
            query = text("""
                SELECT hc.h3_index, hc.res
                FROM user_cell_visits ucv
                JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
                WHERE ucv.user_id = :user_id
                  AND hc.res IN (6, 8)
                  AND ST_Intersects(
                      hc.centroid::geometry,
                      ST_MakeEnvelope(:min_lng, :min_lat, :max_lng, :max_lat, 4326)
                  )
                ORDER BY hc.h3_index
            """)
            result = self.db.execute(query, {
                "user_id": self.user_id,
                "min_lng": min_lng,
                "min_lat": min_lat,
                "max_lng": max_lng,
                "max_lat": max_lat,
            }).fetchall()

        res6, res8 = [], []
        for row in result:
            if row.res == 6:
                res6.append(row.h3_index)
            else:
                res8.append(row.h3_index)

        return {"res6": res6, "res8": res8}

    def get_polygons_in_viewport(
        self,
        min_lng: float,
        min_lat: float,
        max_lng: float,
        max_lat: float,
        zoom: Optional[float] = None,
    ) -> dict:
        """Get H3 cells as GeoJSON polygons within the bounding box.

        Args:
            min_lng: Western longitude bound
            min_lat: Southern latitude bound
            max_lng: Eastern longitude bound
            max_lat: Northern latitude bound
            zoom: Current map zoom level (determines which resolution to return)

        Returns:
            GeoJSON FeatureCollection with polygon features for each H3 cell
        """
        # Determine which resolution to show based on zoom level
        # zoom < 10: show res-6 (larger hexagons, ~3.2km)
        # zoom >= 10: show res-8 (smaller hexagons, ~460m)
        if zoom is not None and zoom < 10:
            target_res = 6
        else:
            target_res = 8

        # SQLite doesn't have PostGIS, so we return all cells
        if self._is_sqlite:
            query = text("""
                SELECT hc.h3_index, hc.res
                FROM user_cell_visits ucv
                JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
                WHERE ucv.user_id = :user_id
                  AND hc.res = :target_res
                ORDER BY hc.h3_index
            """)
            result = self.db.execute(query, {
                "user_id": self.user_id,
                "target_res": target_res,
            }).fetchall()
        else:
            query = text("""
                SELECT hc.h3_index, hc.res
                FROM user_cell_visits ucv
                JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
                WHERE ucv.user_id = :user_id
                  AND hc.res = :target_res
                  AND ST_Intersects(
                      hc.centroid::geometry,
                      ST_MakeEnvelope(:min_lng, :min_lat, :max_lng, :max_lat, 4326)
                  )
                ORDER BY hc.h3_index
            """)
            result = self.db.execute(query, {
                "user_id": self.user_id,
                "target_res": target_res,
                "min_lng": min_lng,
                "min_lat": min_lat,
                "max_lng": max_lng,
                "max_lat": max_lat,
            }).fetchall()

        features = []
        for row in result:
            # Get H3 cell center and boundary
            center_lat, center_lng = h3.cell_to_latlng(row.h3_index)
            boundary = h3.cell_to_boundary(row.h3_index)

            # Calculate circumradius (distance from center to first vertex)
            vertex_lat, vertex_lng = boundary[0]
            radius_meters = _haversine_distance(center_lat, center_lng, vertex_lat, vertex_lng)

            # Create circle polygon that encases the hexagon
            coords = _create_circle_polygon(center_lat, center_lng, radius_meters)

            feature = {
                "type": "Feature",
                "properties": {
                    "h3_index": row.h3_index,
                    "resolution": row.res,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords],
                },
            }
            features.append(feature)

        return {
            "type": "FeatureCollection",
            "features": features,
        }

    def get_visited_country_polygons(
        self,
        min_lng: float,
        min_lat: float,
        max_lng: float,
        max_lat: float,
    ) -> dict:
        """Get visited country geometries as GeoJSON polygons.

        Args:
            min_lng: Western longitude bound
            min_lat: Southern latitude bound
            max_lng: Eastern longitude bound
            max_lat: Northern latitude bound

        Returns:
            GeoJSON FeatureCollection with country polygon features
        """
        if self._is_sqlite:
            # SQLite doesn't support PostGIS, return empty
            return {"type": "FeatureCollection", "features": []}

        query = text("""
            SELECT
                rc.id,
                rc.iso2,
                rc.name,
                ST_AsGeoJSON(rc.geom)::json AS geometry
            FROM regions_country rc
            WHERE rc.id IN (
                SELECT DISTINCT hc.country_id
                FROM user_cell_visits ucv
                JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
                WHERE ucv.user_id = :user_id
                  AND ucv.res = 8
                  AND hc.country_id IS NOT NULL
            )
              AND rc.geom IS NOT NULL
              AND ST_Intersects(
                  rc.geom,
                  ST_MakeEnvelope(:min_lng, :min_lat, :max_lng, :max_lat, 4326)
              )
            ORDER BY rc.name
        """)

        result = self.db.execute(query, {
            "user_id": self.user_id,
            "min_lng": min_lng,
            "min_lat": min_lat,
            "max_lng": max_lng,
            "max_lat": max_lat,
        }).fetchall()

        features = []
        for row in result:
            feature = {
                "type": "Feature",
                "properties": {
                    "id": row.id,
                    "code": row.iso2,
                    "name": row.name,
                    "type": "country",
                },
                "geometry": row.geometry,
            }
            features.append(feature)

        return {
            "type": "FeatureCollection",
            "features": features,
        }

    def get_visited_state_polygons(
        self,
        min_lng: float,
        min_lat: float,
        max_lng: float,
        max_lat: float,
    ) -> dict:
        """Get visited state/region geometries as GeoJSON polygons.

        Args:
            min_lng: Western longitude bound
            min_lat: Southern latitude bound
            max_lng: Eastern longitude bound
            max_lat: Northern latitude bound

        Returns:
            GeoJSON FeatureCollection with state polygon features
        """
        if self._is_sqlite:
            # SQLite doesn't support PostGIS, return empty
            return {"type": "FeatureCollection", "features": []}

        query = text("""
            SELECT
                rs.id,
                rs.code,
                rs.name,
                rc.iso2 AS country_code,
                ST_AsGeoJSON(rs.geom)::json AS geometry
            FROM regions_state rs
            JOIN regions_country rc ON rs.country_id = rc.id
            WHERE rs.id IN (
                SELECT DISTINCT hc.state_id
                FROM user_cell_visits ucv
                JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
                WHERE ucv.user_id = :user_id
                  AND ucv.res = 8
                  AND hc.state_id IS NOT NULL
            )
              AND rs.geom IS NOT NULL
              AND ST_Intersects(
                  rs.geom,
                  ST_MakeEnvelope(:min_lng, :min_lat, :max_lng, :max_lat, 4326)
              )
            ORDER BY rs.name
        """)

        result = self.db.execute(query, {
            "user_id": self.user_id,
            "min_lng": min_lng,
            "min_lat": min_lat,
            "max_lng": max_lng,
            "max_lat": max_lat,
        }).fetchall()

        features = []
        for row in result:
            feature = {
                "type": "Feature",
                "properties": {
                    "id": row.id,
                    "code": f"{row.country_code}-{row.code}" if row.code else None,
                    "name": row.name,
                    "type": "state",
                },
                "geometry": row.geometry,
            }
            features.append(feature)

        return {
            "type": "FeatureCollection",
            "features": features,
        }
