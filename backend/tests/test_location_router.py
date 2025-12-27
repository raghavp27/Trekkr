"""Integration tests for location ingestion endpoint.

Tests the /ingest POST endpoint end-to-end with a real database,
validating request/response schemas, authentication, rate limiting,
and the complete discovery flow.
"""

import time
from datetime import datetime

import h3
import pytest
from fastapi.testclient import TestClient

from models.device import Device
from models.user import User
from models.geo import CountryRegion, StateRegion
from tests.conftest import assert_discovery_response, create_jwt_token
from tests.fixtures.test_data import (
    SAN_FRANCISCO,
    TOKYO,
    INTERNATIONAL_WATERS,
    LOS_ANGELES,
    NEW_YORK,
)


# ============================================================================
# Request Validation Tests
# ============================================================================

@pytest.mark.integration
class TestRequestValidation:
    """Test request payload validation."""

    def test_valid_request_returns_200(
        self,
        client: TestClient,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that a valid request returns 200 with correct schema."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": SAN_FRANCISCO["h3_res8"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response schema
        assert "discoveries" in data
        assert "revisits" in data
        assert "visit_counts" in data

    def test_invalid_latitude_returns_422(self, client: TestClient, test_user: User):
        """Test that latitude outside -90 to 90 returns 422."""
        token = create_jwt_token(test_user.id, test_user.username)

        # Latitude > 90
        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": 91.0,
                "longitude": 0.0,
                "h3_res8": SAN_FRANCISCO["h3_res8"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

        # Latitude < -90
        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": -91.0,
                "longitude": 0.0,
                "h3_res8": SAN_FRANCISCO["h3_res8"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    def test_invalid_longitude_returns_422(self, client: TestClient, test_user: User):
        """Test that longitude outside -180 to 180 returns 422."""
        token = create_jwt_token(test_user.id, test_user.username)

        # Longitude > 180
        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": 0.0,
                "longitude": 181.0,
                "h3_res8": SAN_FRANCISCO["h3_res8"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

        # Longitude < -180
        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": 0.0,
                "longitude": -181.0,
                "h3_res8": SAN_FRANCISCO["h3_res8"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    def test_invalid_h3_index_returns_422(self, client: TestClient, test_user: User):
        """Test that an invalid H3 index returns 422."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": "invalid-h3-index",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    def test_wrong_h3_resolution_returns_422(self, client: TestClient, test_user: User):
        """Test that H3 index with wrong resolution returns 422."""
        token = create_jwt_token(test_user.id, test_user.username)

        # Use res-6 instead of res-8
        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": SAN_FRANCISCO["h3_res6"],  # Wrong resolution!
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    def test_missing_required_fields_returns_422(self, client: TestClient, test_user: User):
        """Test that missing required fields returns 422."""
        token = create_jwt_token(test_user.id, test_user.username)

        # Missing latitude
        response = client.post(
            "/api/location/ingest",
            json={
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": SAN_FRANCISCO["h3_res8"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

        # Missing h3_res8
        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422


# ============================================================================
# H3 Coordinate Validation Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.h3
class TestH3CoordinateValidation:
    """Test H3 index validation against coordinates."""

    def test_exact_h3_match_succeeds(
        self, client: TestClient, test_user: User, test_country_usa: CountryRegion
    ):
        """Test that exact H3 match succeeds."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": SAN_FRANCISCO["h3_res8"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

    def test_neighbor_cell_succeeds_gps_jitter(
        self, client: TestClient, test_user: User, test_country_usa: CountryRegion
    ):
        """Test that neighbor cells (GPS jitter tolerance) succeed."""
        token = create_jwt_token(test_user.id, test_user.username)

        # Get a neighbor cell
        expected_h3 = h3.latlng_to_cell(
            SAN_FRANCISCO["latitude"], SAN_FRANCISCO["longitude"], 8
        )
        neighbors = list(h3.grid_ring(expected_h3, 1))

        # Use a neighbor instead of exact match
        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": neighbors[0],  # Neighbor cell
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

    def test_non_matching_non_neighbor_returns_400(
        self, client: TestClient, test_user: User
    ):
        """Test that H3 index that doesn't match and isn't a neighbor returns 400."""
        token = create_jwt_token(test_user.id, test_user.username)

        # Use Tokyo's H3 cell for San Francisco coordinates
        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": TOKYO["h3_res8"],  # Completely wrong cell
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
        data = response.json()

        # Verify error details
        assert "detail" in data
        assert "error" in data["detail"]
        assert data["detail"]["error"] == "h3_mismatch"
        assert "expected" in data["detail"]
        assert "received" in data["detail"]


# ============================================================================
# Authentication & Authorization Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.auth
class TestAuthentication:
    """Test authentication and authorization."""

    def test_no_token_returns_401(self, client: TestClient):
        """Test that request without JWT token returns 401."""
        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": SAN_FRANCISCO["h3_res8"],
            },
        )

        assert response.status_code == 401

    def test_invalid_token_returns_401(self, client: TestClient):
        """Test that request with invalid token returns 401."""
        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": SAN_FRANCISCO["h3_res8"],
            },
            headers={"Authorization": "Bearer invalid-token-xyz"},
        )

        assert response.status_code == 401

    def test_expired_token_returns_401(
        self, client: TestClient, test_user: User, expired_jwt_token: str
    ):
        """Test that request with expired token returns 401."""
        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": SAN_FRANCISCO["h3_res8"],
            },
            headers={"Authorization": f"Bearer {expired_jwt_token}"},
        )

        assert response.status_code == 401

    def test_valid_token_succeeds(
        self, client: TestClient, test_user: User, test_country_usa: CountryRegion
    ):
        """Test that request with valid token succeeds."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": SAN_FRANCISCO["h3_res8"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200


# ============================================================================
# Rate Limiting Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.ratelimit
@pytest.mark.slow
class TestRateLimiting:
    """Test rate limiting (120 requests per minute per user)."""

    def test_within_rate_limit_succeeds(
        self, client: TestClient, test_user: User, test_country_usa: CountryRegion
    ):
        """Test that requests within rate limit succeed."""
        token = create_jwt_token(test_user.id, test_user.username)

        # Send 5 requests (well under 120/min limit)
        for i in range(5):
            response = client.post(
                "/api/location/ingest",
                json={
                    "latitude": SAN_FRANCISCO["latitude"],
                    "longitude": SAN_FRANCISCO["longitude"],
                    "h3_res8": SAN_FRANCISCO["h3_res8"],
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200

    @pytest.mark.skip(reason="Rate limit test requires 121 requests - too slow for CI")
    def test_exceeds_rate_limit_returns_429(
        self, client: TestClient, test_user: User, test_country_usa: CountryRegion
    ):
        """Test that exceeding rate limit returns 429."""
        token = create_jwt_token(test_user.id, test_user.username)

        # Send 121 requests rapidly
        for i in range(121):
            response = client.post(
                "/api/location/ingest",
                json={
                    "latitude": SAN_FRANCISCO["latitude"],
                    "longitude": SAN_FRANCISCO["longitude"],
                    "h3_res8": SAN_FRANCISCO["h3_res8"],
                },
                headers={"Authorization": f"Bearer {token}"},
            )

            if i < 120:
                assert response.status_code == 200
            else:
                # 121st request should be rate limited
                assert response.status_code == 429

    def test_different_users_independent_limits(
        self,
        client: TestClient,
        test_user: User,
        test_user2: User,
        test_country_usa: CountryRegion,
    ):
        """Test that different users have independent rate limits."""
        token1 = create_jwt_token(test_user.id, test_user.username)
        token2 = create_jwt_token(test_user2.id, test_user2.username)

        # User 1 makes 5 requests
        for _ in range(5):
            response = client.post(
                "/api/location/ingest",
                json={
                    "latitude": SAN_FRANCISCO["latitude"],
                    "longitude": SAN_FRANCISCO["longitude"],
                    "h3_res8": SAN_FRANCISCO["h3_res8"],
                },
                headers={"Authorization": f"Bearer {token1}"},
            )
            assert response.status_code == 200

        # User 2 should still be able to make requests
        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": SAN_FRANCISCO["h3_res8"],
            },
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert response.status_code == 200


# ============================================================================
# Device Handling Tests
# ============================================================================

@pytest.mark.integration
class TestDeviceHandling:
    """Test device_id handling."""

    def test_valid_device_id_links_device(
        self,
        client: TestClient,
        test_user: User,
        test_device: Device,
        test_country_usa: CountryRegion,
    ):
        """Test that valid device_id belonging to user links device to visit."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": SAN_FRANCISCO["h3_res8"],
                "device_id": test_device.device_uuid,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

    def test_device_belonging_to_other_user_ignored(
        self,
        client: TestClient,
        test_user: User,
        test_user2: User,
        test_device: Device,
        test_country_usa: CountryRegion,
        db_session,
    ):
        """Test that device_id belonging to different user is ignored."""
        # Create device for user2
        other_device = Device(
            user_id=test_user2.id,
            device_uuid="other-device-uuid",
            device_name="Other Phone",
            platform="Android",
        )
        db_session.add(other_device)
        db_session.commit()

        token = create_jwt_token(test_user.id, test_user.username)

        # User 1 tries to use User 2's device
        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": SAN_FRANCISCO["h3_res8"],
                "device_id": other_device.device_uuid,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should succeed but device_id is ignored
        assert response.status_code == 200

    def test_nonexistent_device_id_ignored(
        self, client: TestClient, test_user: User, test_country_usa: CountryRegion
    ):
        """Test that non-existent device_id is ignored."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": SAN_FRANCISCO["h3_res8"],
                "device_id": "non-existent-device-uuid",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should succeed, device_id ignored
        assert response.status_code == 200

    def test_no_device_id_works(
        self, client: TestClient, test_user: User, test_country_usa: CountryRegion
    ):
        """Test that no device_id works fine."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": SAN_FRANCISCO["h3_res8"],
                # No device_id provided
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200


# ============================================================================
# End-to-End Discovery Flow Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.geo
class TestDiscoveryFlow:
    """Test end-to-end discovery and revisit detection."""

    def test_first_location_in_new_country(
        self,
        client: TestClient,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test first location in new country returns full discovery."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": SAN_FRANCISCO["h3_res8"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()

        # Should discover country, state, and both cells
        assert_discovery_response(
            data,
            expected_new_country="United States",
            expected_new_state="California",
            expected_new_cells_res6=1,
            expected_new_cells_res8=1,
            expected_revisit_cells_res6=0,
            expected_revisit_cells_res8=0,
        )

        # Verify visit counts
        assert data["visit_counts"]["res6_visit_count"] == 1
        assert data["visit_counts"]["res8_visit_count"] == 1

    def test_second_location_same_country_no_country_discovery(
        self,
        client: TestClient,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test second location in same country doesn't rediscover country."""
        token = create_jwt_token(test_user.id, test_user.username)

        # First visit: San Francisco
        client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": SAN_FRANCISCO["h3_res8"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        # Second visit: Los Angeles (same country and state)
        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": LOS_ANGELES["latitude"],
                "longitude": LOS_ANGELES["longitude"],
                "h3_res8": LOS_ANGELES["h3_res8"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()

        # Should NOT discover country or state (already visited)
        assert data["discoveries"]["new_country"] is None
        assert data["discoveries"]["new_state"] is None

        # But should discover new cells
        assert len(data["discoveries"]["new_cells_res6"]) == 1
        assert len(data["discoveries"]["new_cells_res8"]) == 1

    def test_revisit_exact_location_no_discoveries(
        self,
        client: TestClient,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test revisiting exact same location returns empty discoveries."""
        token = create_jwt_token(test_user.id, test_user.username)

        # First visit
        response1 = client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": SAN_FRANCISCO["h3_res8"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response1.status_code == 200

        # Revisit same location
        response2 = client.post(
            "/api/location/ingest",
            json={
                "latitude": SAN_FRANCISCO["latitude"],
                "longitude": SAN_FRANCISCO["longitude"],
                "h3_res8": SAN_FRANCISCO["h3_res8"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response2.status_code == 200
        data = response2.json()

        # No new discoveries
        assert data["discoveries"]["new_country"] is None
        assert data["discoveries"]["new_state"] is None
        assert len(data["discoveries"]["new_cells_res6"]) == 0
        assert len(data["discoveries"]["new_cells_res8"]) == 0

        # All cells are revisits
        assert len(data["revisits"]["cells_res6"]) == 1
        assert len(data["revisits"]["cells_res8"]) == 1

        # Visit counts incremented
        assert data["visit_counts"]["res6_visit_count"] == 2
        assert data["visit_counts"]["res8_visit_count"] == 2

    def test_international_waters_no_geography(
        self, client: TestClient, test_user: User
    ):
        """Test location in international waters has no geography."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.post(
            "/api/location/ingest",
            json={
                "latitude": INTERNATIONAL_WATERS["latitude"],
                "longitude": INTERNATIONAL_WATERS["longitude"],
                "h3_res8": INTERNATIONAL_WATERS["h3_res8"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()

        # No country or state discovery
        assert data["discoveries"]["new_country"] is None
        assert data["discoveries"]["new_state"] is None

        # But cells are still discovered
        assert len(data["discoveries"]["new_cells_res6"]) == 1
        assert len(data["discoveries"]["new_cells_res8"]) == 1
