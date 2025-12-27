"""Location processing service for H3 cell tracking."""

from datetime import datetime
from typing import Optional, Tuple

import h3
from sqlalchemy import text
from sqlalchemy.orm import Session

from models.geo import CountryRegion, H3Cell, StateRegion
from models.visits import IngestBatch, UserCellVisit


class LocationProcessor:
    """Processes location updates and tracks cell visits."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    def process_location(
        self,
        latitude: float,
        longitude: float,
        h3_res8: str,
        device_id: Optional[int] = None,
        timestamp: Optional[datetime] = None,
    ) -> dict:
        """
        Process a location update and record cell visits.

        Returns discovery summary with new vs. revisited entities.
        """
        timestamp = timestamp or datetime.utcnow()

        # Derive parent res-6 cell from res-8
        h3_res6 = h3.cell_to_parent(h3_res8, 6)

        # Reverse geocode to find country/state
        country_id, state_id = self._reverse_geocode(latitude, longitude)

        # Process both resolutions
        res6_result = self._upsert_cell_visit(
            h3_index=h3_res6,
            res=6,
            latitude=latitude,
            longitude=longitude,
            country_id=country_id,
            state_id=state_id,
            device_id=device_id,
        )

        res8_result = self._upsert_cell_visit(
            h3_index=h3_res8,
            res=8,
            latitude=latitude,
            longitude=longitude,
            country_id=country_id,
            state_id=state_id,
            device_id=device_id,
        )

        # Record audit batch
        self._record_ingest_batch(device_id)

        # Commit transaction
        self.db.commit()

        # Build response
        return self._build_response(
            res6_result=res6_result,
            res8_result=res8_result,
            country_id=country_id,
            state_id=state_id,
        )

    def _reverse_geocode(
        self, latitude: float, longitude: float
    ) -> Tuple[Optional[int], Optional[int]]:
        """Find country and state containing the given point using PostGIS."""
        query = text("""
            WITH point AS (
                SELECT ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) AS geom
            )
            SELECT
                (SELECT id FROM regions_country
                 WHERE ST_Contains(geom, (SELECT geom FROM point))
                 LIMIT 1) AS country_id,
                (SELECT id FROM regions_state
                 WHERE ST_Contains(geom, (SELECT geom FROM point))
                 LIMIT 1) AS state_id
        """)

        result = self.db.execute(
            query, {"lat": latitude, "lon": longitude}
        ).fetchone()

        if result:
            return result.country_id, result.state_id
        return None, None

    def _upsert_cell_visit(
        self,
        h3_index: str,
        res: int,
        latitude: float,
        longitude: float,
        country_id: Optional[int],
        state_id: Optional[int],
        device_id: Optional[int],
    ) -> dict:
        """Upsert H3Cell and UserCellVisit records, return insert/update status."""

        # Upsert H3Cell (global registry)
        h3_cell_query = text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid,
                                  first_visited_at, last_visited_at, visit_count)
            VALUES (:h3_index, :res, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                    NOW(), NOW(), 1)
            ON CONFLICT (h3_index)
            DO UPDATE SET
                last_visited_at = NOW(),
                visit_count = h3_cells.visit_count + 1,
                country_id = COALESCE(h3_cells.country_id, EXCLUDED.country_id),
                state_id = COALESCE(h3_cells.state_id, EXCLUDED.state_id)
            RETURNING h3_index, (xmax = 0) AS was_inserted
        """)

        self.db.execute(h3_cell_query, {
            "h3_index": h3_index,
            "res": res,
            "country_id": country_id,
            "state_id": state_id,
            "lat": latitude,
            "lon": longitude,
        })

        # Upsert UserCellVisit (per-user tracking)
        user_visit_query = text("""
            INSERT INTO user_cell_visits
                (user_id, device_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :device_id, :h3_index, :res, NOW(), NOW(), 1)
            ON CONFLICT (user_id, h3_index)
            DO UPDATE SET
                last_visited_at = NOW(),
                visit_count = user_cell_visits.visit_count + 1,
                device_id = COALESCE(EXCLUDED.device_id, user_cell_visits.device_id)
            RETURNING h3_index, res, visit_count, (xmax = 0) AS was_inserted
        """)

        result = self.db.execute(user_visit_query, {
            "user_id": self.user_id,
            "device_id": device_id,
            "h3_index": h3_index,
            "res": res,
        }).fetchone()

        return {
            "h3_index": result.h3_index,
            "res": result.res,
            "visit_count": result.visit_count,
            "is_new": result.was_inserted,
        }

    def _record_ingest_batch(self, device_id: Optional[int]) -> None:
        """Record audit entry for this ingestion."""
        batch = IngestBatch(
            user_id=self.user_id,
            device_id=device_id,
            cells_count=2,  # res-6 + res-8
            res_min=6,
            res_max=8,
        )
        self.db.add(batch)

    def _build_response(
        self,
        res6_result: dict,
        res8_result: dict,
        country_id: Optional[int],
        state_id: Optional[int],
    ) -> dict:
        """Build the discovery/revisit response."""
        discoveries = {
            "new_country": None,
            "new_state": None,
            "new_cells_res6": [],
            "new_cells_res8": [],
        }
        revisits = {
            "cells_res6": [],
            "cells_res8": [],
        }

        # Categorize res-6 cell
        if res6_result["is_new"]:
            discoveries["new_cells_res6"].append(res6_result["h3_index"])
        else:
            revisits["cells_res6"].append(res6_result["h3_index"])

        # Categorize res-8 cell
        if res8_result["is_new"]:
            discoveries["new_cells_res8"].append(res8_result["h3_index"])
        else:
            revisits["cells_res8"].append(res8_result["h3_index"])

        # Check if this is user's first visit to country/state
        # (Only if res-8 cell is new - indicates potential new region)
        if res8_result["is_new"]:
            if country_id:
                country = self.db.query(CountryRegion).filter(
                    CountryRegion.id == country_id
                ).first()
                if country:
                    # Check if user has any other cells in this country
                    other_cells = self.db.execute(text("""
                        SELECT ucv.h3_index FROM user_cell_visits ucv
                        JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
                        WHERE ucv.user_id = :user_id
                          AND hc.country_id = :country_id
                          AND ucv.res = 8
                          AND ucv.h3_index != :current_h3
                        LIMIT 1
                    """), {
                        "user_id": self.user_id,
                        "country_id": country_id,
                        "current_h3": res8_result["h3_index"],
                    }).fetchone()

                    if not other_cells:
                        discoveries["new_country"] = {
                            "id": country.id,
                            "name": country.name,
                            "iso2": country.iso2,
                        }

            if state_id:
                state = self.db.query(StateRegion).filter(
                    StateRegion.id == state_id
                ).first()
                if state:
                    other_cells = self.db.execute(text("""
                        SELECT 1 FROM user_cell_visits ucv
                        JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
                        WHERE ucv.user_id = :user_id
                          AND hc.state_id = :state_id
                          AND ucv.res = 8
                          AND ucv.h3_index != :current_h3
                        LIMIT 1
                    """), {
                        "user_id": self.user_id,
                        "state_id": state_id,
                        "current_h3": res8_result["h3_index"],
                    }).fetchone()

                    if not other_cells:
                        discoveries["new_state"] = {
                            "id": state.id,
                            "name": state.name,
                            "code": state.code,
                        }

        return {
            "discoveries": discoveries,
            "revisits": revisits,
            "visit_counts": {
                "res6_visit_count": res6_result["visit_count"],
                "res8_visit_count": res8_result["visit_count"],
            },
        }
