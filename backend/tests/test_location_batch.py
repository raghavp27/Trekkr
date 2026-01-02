"""Tests for batch location ingestion endpoint."""

import pytest
from datetime import datetime, timedelta
from fastapi import status
import h3


class TestBatchLocationIngest:
    """Tests for POST /api/v1/location/ingest/batch"""

    def test_batch_ingest_success(self, client, auth_headers, db_session):
        """Happy path: multiple valid locations are all processed."""
        # Generate 5 locations in San Francisco area with larger spacing
        # Use 0.01 degree spacing (~1.1km) to ensure different H3 res-8 cells
        base_lat, base_lon = 37.7749, -122.4194
        locations = []
        for i in range(5):
            lat = base_lat + (i * 0.01)
            lon = base_lon + (i * 0.01)
            h3_index = h3.latlng_to_cell(lat, lon, 8)
            locations.append({
                "latitude": lat,
                "longitude": lon,
                "h3_res8": h3_index,
                "timestamp": (datetime.utcnow() - timedelta(minutes=5-i)).isoformat(),
            })

        response = client.post(
            "/api/v1/location/ingest/batch",
            json={"locations": locations},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["processed"] == 5
        assert data["skipped"] == 0
        assert data["skipped_reasons"] == []

    def test_batch_ingest_empty_rejected(self, client, auth_headers):
        """Empty locations array returns 422."""
        response = client.post(
            "/api/v1/location/ingest/batch",
            json={"locations": []},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_batch_ingest_max_100_locations(self, client, auth_headers):
        """101 locations returns 422."""
        base_lat, base_lon = 37.7749, -122.4194
        locations = []
        for i in range(101):
            lat = base_lat + (i * 0.0001)
            lon = base_lon + (i * 0.0001)
            h3_index = h3.latlng_to_cell(lat, lon, 8)
            locations.append({
                "latitude": lat,
                "longitude": lon,
                "h3_res8": h3_index,
            })

        response = client.post(
            "/api/v1/location/ingest/batch",
            json={"locations": locations},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_batch_ingest_partial_success(self, client, auth_headers):
        """Mix of valid/invalid: valid processed, invalid skipped with reasons."""
        base_lat, base_lon = 37.7749, -122.4194
        h3_valid = h3.latlng_to_cell(base_lat, base_lon, 8)

        # Location in Tokyo but with SF H3 index (mismatch)
        h3_mismatched = h3.latlng_to_cell(35.6762, 139.6503, 8)

        locations = [
            {"latitude": base_lat, "longitude": base_lon, "h3_res8": h3_valid},  # Valid
            {"latitude": 35.6762, "longitude": 139.6503, "h3_res8": h3_valid},  # H3 mismatch
            {"latitude": base_lat + 0.01, "longitude": base_lon + 0.01,
             "h3_res8": h3.latlng_to_cell(base_lat + 0.01, base_lon + 0.01, 8)},  # Valid (larger spacing)
        ]

        response = client.post(
            "/api/v1/location/ingest/batch",
            json={"locations": locations},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["processed"] == 2
        assert data["skipped"] == 1
        assert len(data["skipped_reasons"]) == 1
        assert data["skipped_reasons"][0]["index"] == 1
        assert data["skipped_reasons"][0]["reason"] == "h3_mismatch"

    def test_batch_ingest_deduplicates_cells(self, client, auth_headers, db_session):
        """Same H3 cell twice: only first processed (deduped)."""
        lat, lon = 37.7749, -122.4194
        h3_index = h3.latlng_to_cell(lat, lon, 8)

        locations = [
            {"latitude": lat, "longitude": lon, "h3_res8": h3_index,
             "timestamp": "2024-12-28T10:00:00Z"},
            {"latitude": lat, "longitude": lon, "h3_res8": h3_index,
             "timestamp": "2024-12-28T10:05:00Z"},  # Duplicate, should be ignored
        ]

        response = client.post(
            "/api/v1/location/ingest/batch",
            json={"locations": locations},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Only 1 unique cell processed (duplicate silently deduped, not "skipped")
        assert data["processed"] == 1
        assert data["skipped"] == 0

    def test_batch_ingest_returns_discovery_structure(
        self, client, auth_headers, db_session
    ):
        """Response includes discovery structure with cell counts."""
        lat, lon = 37.7749, -122.4194  # San Francisco
        h3_index = h3.latlng_to_cell(lat, lon, 8)

        response = client.post(
            "/api/v1/location/ingest/batch",
            json={"locations": [{"latitude": lat, "longitude": lon, "h3_res8": h3_index}]},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert "discoveries" in data
        assert "new_countries" in data["discoveries"]
        assert "new_regions" in data["discoveries"]
        assert "new_cells_res6" in data["discoveries"]
        assert "new_cells_res8" in data["discoveries"]
        assert data["discoveries"]["new_cells_res8"] >= 1

    def test_batch_ingest_returns_achievements_list(
        self, client, auth_headers, db_session
    ):
        """Response includes achievements list (may be empty)."""
        lat, lon = 37.7749, -122.4194
        h3_index = h3.latlng_to_cell(lat, lon, 8)

        response = client.post(
            "/api/v1/location/ingest/batch",
            json={"locations": [{"latitude": lat, "longitude": lon, "h3_res8": h3_index}]},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify achievements structure exists (may be empty list)
        assert "achievements_unlocked" in data
        assert isinstance(data["achievements_unlocked"], list)

    def test_batch_ingest_unauthenticated(self, client):
        """No token returns 401."""
        response = client.post(
            "/api/v1/location/ingest/batch",
            json={"locations": [{"latitude": 0, "longitude": 0, "h3_res8": "88283082bffffff"}]},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_batch_ingest_idempotent_cells(self, client, auth_headers, db_session):
        """Re-sending same cells increments visit_count, not duplicates."""
        lat, lon = 37.7749, -122.4194
        h3_index = h3.latlng_to_cell(lat, lon, 8)
        payload = {"locations": [{"latitude": lat, "longitude": lon, "h3_res8": h3_index}]}

        # First request
        response1 = client.post(
            "/api/v1/location/ingest/batch",
            json=payload,
            headers=auth_headers,
        )
        assert response1.status_code == status.HTTP_200_OK
        assert response1.json()["discoveries"]["new_cells_res8"] == 1

        # Second request with same cell
        response2 = client.post(
            "/api/v1/location/ingest/batch",
            json=payload,
            headers=auth_headers,
        )
        assert response2.status_code == status.HTTP_200_OK
        # Cell is no longer new (revisit)
        assert response2.json()["discoveries"]["new_cells_res8"] == 0
        assert response2.json()["processed"] == 1

    def test_batch_ingest_with_device_metadata(self, client, auth_headers, db_session):
        """Device metadata at batch level is applied."""
        lat, lon = 37.7749, -122.4194
        h3_index = h3.latlng_to_cell(lat, lon, 8)

        response = client.post(
            "/api/v1/location/ingest/batch",
            json={
                "locations": [{"latitude": lat, "longitude": lon, "h3_res8": h3_index}],
                "device_uuid": "test-device-123",
                "device_name": "Test iPhone",
                "platform": "ios",
            },
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["processed"] == 1
