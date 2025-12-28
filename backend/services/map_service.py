"""Map service for retrieving user's visited areas."""

from sqlalchemy import text
from sqlalchemy.orm import Session


class MapService:
    """Service for map-related queries."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

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
