"""Stats service for retrieving user travel statistics."""

from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from models.user import User


class StatsService:
    """Service for stats-related queries."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    def get_countries(
        self,
        sort_by: Literal["coverage_pct", "first_visited_at", "last_visited_at", "name"] = "last_visited_at",
        order: Literal["asc", "desc"] = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Get countries the user has visited with coverage statistics."""
        # Validate sort_by to prevent SQL injection
        valid_sort_fields = {
            "coverage_pct": "(COUNT(ucv.id)::float / COALESCE(c.land_cells_total_resolution8, 1))",
            "first_visited_at": "first_visited_at",
            "last_visited_at": "last_visited_at",
            "name": "c.name",
        }
        sort_field = valid_sort_fields.get(sort_by, "last_visited_at")
        order_dir = "DESC" if order == "desc" else "ASC"

        # Get total count first
        count_query = text("""
            SELECT COUNT(DISTINCT c.id) as total
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            JOIN regions_country c ON hc.country_id = c.id
            WHERE ucv.user_id = :user_id AND ucv.res = 8
        """)
        total = self.db.execute(count_query, {"user_id": self.user_id}).scalar() or 0

        # Get paginated results with coverage
        data_query = text(f"""
            SELECT
                c.iso2 AS code,
                c.name,
                COUNT(ucv.id) AS cells_visited,
                COALESCE(c.land_cells_total_resolution8, 1) AS cells_total,
                MIN(ucv.first_visited_at) AS first_visited_at,
                MAX(ucv.last_visited_at) AS last_visited_at
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            JOIN regions_country c ON hc.country_id = c.id
            WHERE ucv.user_id = :user_id AND ucv.res = 8
            GROUP BY c.id, c.iso2, c.name, c.land_cells_total_resolution8
            ORDER BY {sort_field} {order_dir}
            LIMIT :limit OFFSET :offset
        """)

        rows = self.db.execute(data_query, {
            "user_id": self.user_id,
            "limit": limit,
            "offset": offset,
        }).fetchall()

        countries = []
        for row in rows:
            coverage_pct = row.cells_visited / row.cells_total if row.cells_total > 0 else 0.0
            countries.append({
                "code": row.code,
                "name": row.name,
                "coverage_pct": round(coverage_pct, 6),
                "first_visited_at": row.first_visited_at,
                "last_visited_at": row.last_visited_at,
            })

        return {
            "total_countries_visited": total,
            "countries": countries,
        }

    def get_regions(
        self,
        sort_by: Literal["coverage_pct", "first_visited_at", "last_visited_at", "name"] = "last_visited_at",
        order: Literal["asc", "desc"] = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Get regions/states the user has visited with coverage statistics."""
        # Validate sort_by to prevent SQL injection
        valid_sort_fields = {
            "coverage_pct": "(COUNT(ucv.id)::float / COALESCE(s.land_cells_total_resolution8, 1))",
            "first_visited_at": "first_visited_at",
            "last_visited_at": "last_visited_at",
            "name": "s.name",
        }
        sort_field = valid_sort_fields.get(sort_by, "last_visited_at")
        order_dir = "DESC" if order == "desc" else "ASC"

        # Get total count first
        count_query = text("""
            SELECT COUNT(DISTINCT s.id) as total
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            JOIN regions_state s ON hc.state_id = s.id
            WHERE ucv.user_id = :user_id AND ucv.res = 8
        """)
        total = self.db.execute(count_query, {"user_id": self.user_id}).scalar() or 0

        # Get paginated results with coverage
        data_query = text(f"""
            SELECT
                CONCAT(c.iso2, '-', s.code) AS code,
                s.name,
                c.iso2 AS country_code,
                c.name AS country_name,
                COUNT(ucv.id) AS cells_visited,
                COALESCE(s.land_cells_total_resolution8, 1) AS cells_total,
                MIN(ucv.first_visited_at) AS first_visited_at,
                MAX(ucv.last_visited_at) AS last_visited_at
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            JOIN regions_state s ON hc.state_id = s.id
            JOIN regions_country c ON s.country_id = c.id
            WHERE ucv.user_id = :user_id AND ucv.res = 8
            GROUP BY s.id, s.code, s.name, s.land_cells_total_resolution8, c.id, c.iso2, c.name
            ORDER BY {sort_field} {order_dir}
            LIMIT :limit OFFSET :offset
        """)

        rows = self.db.execute(data_query, {
            "user_id": self.user_id,
            "limit": limit,
            "offset": offset,
        }).fetchall()

        regions = []
        for row in rows:
            coverage_pct = row.cells_visited / row.cells_total if row.cells_total > 0 else 0.0
            regions.append({
                "code": row.code,
                "name": row.name,
                "country_code": row.country_code,
                "country_name": row.country_name,
                "coverage_pct": round(coverage_pct, 6),
                "first_visited_at": row.first_visited_at,
                "last_visited_at": row.last_visited_at,
            })

        return {
            "total_regions_visited": total,
            "regions": regions,
        }

    def get_overview(self) -> dict:
        """Get comprehensive profile overview for a user.

        Returns user info, aggregate stats, and recent countries/regions.
        Uses optimized SQL queries for performance.

        Returns:
            dict with keys: user, stats, recent_countries, recent_regions
        """
        # Fetch user info
        user = self.db.query(User).filter(User.id == self.user_id).first()
        if not user:
            raise ValueError(f"User {self.user_id} not found")

        # Execute main stats query
        stats_query = text("""
            WITH user_stats AS (
              SELECT
                COUNT(DISTINCT CASE WHEN res = 6 THEN h3_index END) as cells_res6,
                COUNT(DISTINCT CASE WHEN res = 8 THEN h3_index END) as cells_res8,
                MIN(first_visited_at) as first_visit,
                MAX(last_visited_at) as last_visit,
                COALESCE(SUM(visit_count), 0) as total_visits
              FROM user_cell_visits
              WHERE user_id = :user_id
            ),
            country_stats AS (
              SELECT COUNT(DISTINCT hc.country_id) as countries
              FROM user_cell_visits ucv
              JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
              WHERE ucv.user_id = :user_id AND ucv.res = 8
            ),
            region_stats AS (
              SELECT COUNT(DISTINCT hc.state_id) as regions
              FROM user_cell_visits ucv
              JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
              WHERE ucv.user_id = :user_id AND ucv.res = 8 AND hc.state_id IS NOT NULL
            )
            SELECT
              us.cells_res6,
              us.cells_res8,
              us.first_visit,
              us.last_visit,
              us.total_visits,
              cs.countries,
              rs.regions
            FROM user_stats us
            CROSS JOIN country_stats cs
            CROSS JOIN region_stats rs
        """)

        stats_row = self.db.execute(stats_query, {"user_id": self.user_id}).fetchone()

        # Fetch recent countries
        countries_query = text("""
            SELECT
              rc.iso2 as code,
              rc.name,
              MAX(ucv.last_visited_at) as visited_at
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            JOIN regions_country rc ON hc.country_id = rc.id
            WHERE ucv.user_id = :user_id AND ucv.res = 8
            GROUP BY rc.id, rc.iso2, rc.name
            ORDER BY visited_at DESC
            LIMIT 3
        """)

        countries_rows = self.db.execute(countries_query, {"user_id": self.user_id}).fetchall()

        # Fetch recent regions
        regions_query = text("""
            SELECT
              CONCAT(rc.iso2, '-', rs.code) as code,
              rs.name,
              rc.name as country_name,
              MAX(ucv.last_visited_at) as visited_at
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            JOIN regions_state rs ON hc.state_id = rs.id
            JOIN regions_country rc ON rs.country_id = rc.id
            WHERE ucv.user_id = :user_id AND ucv.res = 8
            GROUP BY rs.id, rs.code, rs.name, rc.iso2, rc.name
            ORDER BY visited_at DESC
            LIMIT 3
        """)

        regions_rows = self.db.execute(regions_query, {"user_id": self.user_id}).fetchall()

        # Build response structure
        return {
            "user": {
                "id": user.id,
                "username": user.username,
                "created_at": user.created_at,
            },
            "stats": {
                "countries_visited": stats_row.countries or 0,
                "regions_visited": stats_row.regions or 0,
                "cells_visited_res6": stats_row.cells_res6 or 0,
                "cells_visited_res8": stats_row.cells_res8 or 0,
                "total_visit_count": stats_row.total_visits or 0,
                "first_visit_at": stats_row.first_visit,
                "last_visit_at": stats_row.last_visit,
            },
            "recent_countries": [
                {
                    "code": row.code,
                    "name": row.name,
                    "visited_at": row.visited_at,
                }
                for row in countries_rows
            ],
            "recent_regions": [
                {
                    "code": row.code,
                    "name": row.name,
                    "country_name": row.country_name,
                    "visited_at": row.visited_at,
                }
                for row in regions_rows
            ],
        }
