"""Location processing service for H3 cell tracking."""

from datetime import datetime, timezone
from typing import Optional, Tuple

import h3
from sqlalchemy import text
from sqlalchemy.orm import Session

from models.device import Device
from models.geo import CountryRegion, H3Cell, StateRegion
from models.visits import IngestBatch, UserCellVisit
from services.achievement_service import AchievementService


class LocationProcessor:
    """Processes location updates and tracks cell visits."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    def _ensure_device(
        self,
        device_uuid: Optional[str] = None,
        device_name: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> int:
        """Get or create user's single device."""
        device = self.db.query(Device).filter(Device.user_id == self.user_id).first()

        if not device:
            # Create first device
            device = Device(
                user_id=self.user_id,
                device_uuid=device_uuid,
                device_name=device_name or "My Phone",
                platform=platform or "unknown",
            )
            self.db.add(device)
            self.db.flush()
        else:
            # Update metadata if provided
            if device_uuid and device.device_uuid != device_uuid:
                device.device_uuid = device_uuid
            if device_name:
                device.device_name = device_name
            if platform:
                device.platform = platform

        return device.id

    def _validate_and_dedupe_batch(
        self,
        locations: list,
    ) -> tuple[list[dict], list[dict]]:
        """
        Validate locations and dedupe by H3 res-8.

        Returns:
            (valid_locations, skipped_with_reasons)

        Each valid_location dict contains:
            - latitude, longitude, h3_res8, timestamp
            - h3_res6 (derived parent)
        """
        valid = []
        skipped = []
        seen_cells = set()

        for idx, loc in enumerate(locations):
            # Check H3 matches coordinates (with neighbor tolerance)
            expected_h3 = h3.latlng_to_cell(loc.latitude, loc.longitude, 8)
            if loc.h3_res8 != expected_h3:
                neighbors = h3.grid_ring(expected_h3, 1)
                if loc.h3_res8 not in neighbors:
                    skipped.append({"index": idx, "reason": "h3_mismatch"})
                    continue

            # Dedupe: keep first occurrence
            if loc.h3_res8 in seen_cells:
                continue
            seen_cells.add(loc.h3_res8)

            # Derive res-6 parent
            h3_res6 = h3.cell_to_parent(loc.h3_res8, 6)

            valid.append({
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "h3_res8": loc.h3_res8,
                "h3_res6": h3_res6,
                "timestamp": loc.timestamp or datetime.now(timezone.utc),
            })

        return valid, skipped

    def _get_existing_visits(self) -> dict:
        """
        Pre-query user's existing countries, states, and cells.

        Returns dict with sets:
            - country_ids: set[int]
            - state_ids: set[int]
            - h3_res6: set[str]
            - h3_res8: set[str]
        """
        # Get visited country and state IDs
        geo_query = text("""
            SELECT DISTINCT hc.country_id, hc.state_id
            FROM user_cell_visits ucv
            JOIN h3_cells hc ON ucv.h3_index = hc.h3_index
            WHERE ucv.user_id = :user_id AND ucv.res = 8
        """)
        geo_results = self.db.execute(geo_query, {"user_id": self.user_id}).fetchall()

        country_ids = {r.country_id for r in geo_results if r.country_id}
        state_ids = {r.state_id for r in geo_results if r.state_id}

        # Get visited H3 cells
        cells_query = text("""
            SELECT h3_index, res FROM user_cell_visits
            WHERE user_id = :user_id
        """)
        cells_results = self.db.execute(cells_query, {"user_id": self.user_id}).fetchall()

        h3_res6 = {r.h3_index for r in cells_results if r.res == 6}
        h3_res8 = {r.h3_index for r in cells_results if r.res == 8}

        return {
            "country_ids": country_ids,
            "state_ids": state_ids,
            "h3_res6": h3_res6,
            "h3_res8": h3_res8,
        }

    def _batch_reverse_geocode(
        self,
        locations: list[dict],
    ) -> dict[str, tuple[Optional[int], Optional[int]]]:
        """
        Reverse geocode unique res-6 cells.

        Args:
            locations: List of location dicts with h3_res6, latitude, longitude

        Returns:
            Dict mapping h3_res6 -> (country_id, state_id)
        """
        # Group by unique res-6 cells, pick first location as representative point
        res6_representatives = {}
        for loc in locations:
            if loc["h3_res6"] not in res6_representatives:
                res6_representatives[loc["h3_res6"]] = (loc["latitude"], loc["longitude"])

        if not res6_representatives:
            return {}

        # Build query for all unique res-6 cells
        # Use a single query with multiple points for efficiency
        geocode_results = {}

        for h3_res6, (lat, lon) in res6_representatives.items():
            country_id, state_id = self._reverse_geocode(lat, lon)
            geocode_results[h3_res6] = (country_id, state_id)

        return geocode_results

    def _bulk_upsert_cells_and_visits(
        self,
        locations: list[dict],
        geocode_map: dict[str, tuple],
        existing_visits: dict,
        device_id: int,
    ) -> dict:
        """
        Bulk upsert cells and visits using PostgreSQL arrays.

        Returns dict with discovery counts:
            - new_cells_res6: int
            - new_cells_res8: int
            - new_country_ids: set[int]
            - new_state_ids: set[int]
        """
        # Prepare data for both resolutions
        res8_data = []
        res6_data = []
        res6_seen = set()

        for loc in locations:
            country_id, state_id = geocode_map.get(loc["h3_res6"], (None, None))

            # Res-8 cell data
            res8_data.append({
                "h3_index": loc["h3_res8"],
                "res": 8,
                "country_id": country_id,
                "state_id": state_id,
                "lat": loc["latitude"],
                "lon": loc["longitude"],
                "timestamp": loc["timestamp"],
            })

            # Res-6 cell data (dedupe within batch)
            if loc["h3_res6"] not in res6_seen:
                res6_seen.add(loc["h3_res6"])
                # Use centroid of res-6 cell
                res6_lat, res6_lon = h3.cell_to_latlng(loc["h3_res6"])
                res6_data.append({
                    "h3_index": loc["h3_res6"],
                    "res": 6,
                    "country_id": country_id,
                    "state_id": state_id,
                    "lat": res6_lat,
                    "lon": res6_lon,
                    "timestamp": loc["timestamp"],
                })

        # Combine all cells for bulk insert
        all_cells = res6_data + res8_data

        # Bulk upsert h3_cells
        h3_cells_query = text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid,
                                  first_visited_at, last_visited_at, visit_count)
            VALUES (:h3_index, :res, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                    :timestamp, :timestamp, 1)
            ON CONFLICT (h3_index)
            DO UPDATE SET
                last_visited_at = GREATEST(h3_cells.last_visited_at, EXCLUDED.last_visited_at),
                visit_count = h3_cells.visit_count + 1,
                country_id = COALESCE(h3_cells.country_id, EXCLUDED.country_id),
                state_id = COALESCE(h3_cells.state_id, EXCLUDED.state_id)
        """)

        for cell in all_cells:
            self.db.execute(h3_cells_query, cell)

        # Bulk upsert user_cell_visits and track new cells
        user_visits_query = text("""
            INSERT INTO user_cell_visits
                (user_id, device_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :device_id, :h3_index, :res, :timestamp, :timestamp, 1)
            ON CONFLICT (user_id, h3_index)
            DO UPDATE SET
                last_visited_at = GREATEST(user_cell_visits.last_visited_at, EXCLUDED.last_visited_at),
                visit_count = user_cell_visits.visit_count + 1,
                device_id = COALESCE(EXCLUDED.device_id, user_cell_visits.device_id)
            RETURNING h3_index, res, (xmax = 0) AS was_inserted
        """)

        new_cells_res6 = 0
        new_cells_res8 = 0
        new_country_ids = set()
        new_state_ids = set()

        for cell in all_cells:
            result = self.db.execute(user_visits_query, {
                "user_id": self.user_id,
                "device_id": device_id,
                "h3_index": cell["h3_index"],
                "res": cell["res"],
                "timestamp": cell["timestamp"],
            }).fetchone()

            if result.was_inserted:
                if result.res == 6:
                    new_cells_res6 += 1
                else:
                    new_cells_res8 += 1

                    # Check for new country/state discoveries (only on res-8)
                    country_id = cell["country_id"]
                    state_id = cell["state_id"]

                    if country_id and country_id not in existing_visits["country_ids"]:
                        new_country_ids.add(country_id)
                        existing_visits["country_ids"].add(country_id)  # Don't rediscover

                    if state_id and state_id not in existing_visits["state_ids"]:
                        new_state_ids.add(state_id)
                        existing_visits["state_ids"].add(state_id)  # Don't rediscover

        return {
            "new_cells_res6": new_cells_res6,
            "new_cells_res8": new_cells_res8,
            "new_country_ids": new_country_ids,
            "new_state_ids": new_state_ids,
        }

    def process_batch(
        self,
        locations: list,
        device_uuid: Optional[str] = None,
        device_name: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> dict:
        """
        Process a batch of locations efficiently.

        Args:
            locations: List of BatchLocationItem objects
            device_uuid: Optional device identifier
            device_name: Optional device name
            platform: Optional platform (ios/android/web)

        Returns:
            Dict with processed count, skipped info, discoveries, achievements
        """
        # Step 1: Validate and deduplicate
        valid_locations, skipped = self._validate_and_dedupe_batch(locations)

        if not valid_locations:
            return {
                "processed": 0,
                "skipped": len(skipped),
                "skipped_reasons": skipped,
                "discoveries": {
                    "new_countries": [],
                    "new_regions": [],
                    "new_cells_res6": 0,
                    "new_cells_res8": 0,
                },
                "achievements_unlocked": [],
            }

        # Step 2: Ensure device exists
        device_id = self._ensure_device(device_uuid, device_name, platform)

        # Step 3: Pre-query existing visits
        existing_visits = self._get_existing_visits()

        # Step 4: Batch reverse geocode
        geocode_map = self._batch_reverse_geocode(valid_locations)

        # Step 5: Bulk upsert cells and visits
        upsert_results = self._bulk_upsert_cells_and_visits(
            valid_locations, geocode_map, existing_visits, device_id
        )

        # Step 6: Record ingest batch for audit
        batch = IngestBatch(
            user_id=self.user_id,
            device_id=device_id,
            cells_count=len(valid_locations) * 2,  # res-6 + res-8 per location
            res_min=6,
            res_max=8,
        )
        self.db.add(batch)

        # Step 7: Check achievements (once at end)
        achievement_service = AchievementService(self.db, self.user_id)
        newly_unlocked = achievement_service.check_and_unlock()

        # Step 8: Commit transaction
        self.db.commit()

        # Step 9: Build response with country/state details
        new_countries = []
        if upsert_results["new_country_ids"]:
            countries = self.db.query(CountryRegion).filter(
                CountryRegion.id.in_(upsert_results["new_country_ids"])
            ).all()
            new_countries = [
                {"id": c.id, "name": c.name, "iso2": c.iso2}
                for c in countries
            ]

        new_regions = []
        if upsert_results["new_state_ids"]:
            states = self.db.query(StateRegion).filter(
                StateRegion.id.in_(upsert_results["new_state_ids"])
            ).all()
            new_regions = [
                {"id": s.id, "name": s.name, "code": s.code}
                for s in states
            ]

        return {
            "processed": len(valid_locations),
            "skipped": len(skipped),
            "skipped_reasons": skipped,
            "discoveries": {
                "new_countries": new_countries,
                "new_regions": new_regions,
                "new_cells_res6": upsert_results["new_cells_res6"],
                "new_cells_res8": upsert_results["new_cells_res8"],
            },
            "achievements_unlocked": [
                {
                    "code": a.code,
                    "name": a.name,
                    "description": a.description,
                }
                for a in newly_unlocked
            ],
        }

    def process_location(
        self,
        latitude: float,
        longitude: float,
        h3_res8: str,
        device_uuid: Optional[str] = None,
        device_name: Optional[str] = None,
        platform: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> dict:
        """
        Process a location update and record cell visits.

        Returns discovery summary with new vs. revisited entities.
        """
        timestamp = timestamp or datetime.now(timezone.utc)

        # Ensure device exists (auto-create if first time)
        device_id = self._ensure_device(device_uuid, device_name, platform)

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

        # Check and unlock achievements
        achievement_service = AchievementService(self.db, self.user_id)
        newly_unlocked = achievement_service.check_and_unlock()

        # Commit transaction
        self.db.commit()

        # Build response
        response = self._build_response(
            res6_result=res6_result,
            res8_result=res8_result,
            country_id=country_id,
            state_id=state_id,
        )

        # Add achievements to response
        response["achievements_unlocked"] = [
            {
                "code": a.code,
                "name": a.name,
                "description": a.description,
            }
            for a in newly_unlocked
        ]

        return response

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
