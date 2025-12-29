"""Stats service for retrieving user travel statistics."""

from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session


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
