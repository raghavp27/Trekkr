"""Integration tests for map endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from models.user import User
from models.geo import CountryRegion, StateRegion
from tests.conftest import create_jwt_token
from tests.fixtures.test_data import SAN_FRANCISCO


@pytest.mark.integration
class TestMapSummaryEndpoint:
    """Test GET /api/v1/map/summary endpoint."""

    def test_unauthenticated_returns_401(self, client: TestClient):
        """Test that unauthenticated request returns 401."""
        response = client.get("/api/v1/map/summary")
        assert response.status_code == 401

    def test_authenticated_empty_user_returns_200(
        self, client: TestClient, test_user: User
    ):
        """Test that authenticated user with no visits gets empty response."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/summary",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["countries"] == []
        assert data["regions"] == []

    def test_authenticated_with_visits_returns_data(
        self,
        client: TestClient,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that user with visits gets their data."""
        # Create visit
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, first_visited_at, last_visited_at, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), NOW(), NOW(), 1)
        """), {
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": SAN_FRANCISCO["longitude"],
            "lat": SAN_FRANCISCO["latitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3_index": SAN_FRANCISCO["h3_res8"]})
        db_session.commit()

        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/summary",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["countries"]) == 1
        assert data["countries"][0]["code"] == "US"
        assert len(data["regions"]) == 1
        assert data["regions"][0]["code"] == "US-CA"


@pytest.mark.integration
class TestMapCellsEndpoint:
    """Test GET /api/v1/map/cells endpoint."""

    def test_unauthenticated_returns_401(self, client: TestClient):
        """Test that unauthenticated request returns 401."""
        response = client.get(
            "/api/v1/map/cells",
            params={"min_lng": -123, "min_lat": 37, "max_lng": -122, "max_lat": 38},
        )
        assert response.status_code == 401

    def test_missing_params_returns_422(self, client: TestClient, test_user: User):
        """Test that missing bbox params returns 422."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/cells",
            params={"min_lng": -123},  # Missing other params
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    def test_invalid_bbox_returns_400(self, client: TestClient, test_user: User):
        """Test that invalid bbox (min > max) returns 400."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/cells",
            params={
                "min_lng": -122,  # min > max
                "min_lat": 37,
                "max_lng": -123,
                "max_lat": 38,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    def test_bbox_too_large_returns_400(self, client: TestClient, test_user: User):
        """Test that bbox spanning > 180 degrees returns 400."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/cells",
            params={
                "min_lng": -180,
                "min_lat": 0,
                "max_lng": 90,  # 270 degree span
                "max_lat": 10,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    def test_valid_request_returns_cells(
        self,
        client: TestClient,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test valid request returns cells in viewport."""
        # Create visits
        for h3_index, res in [
            (SAN_FRANCISCO["h3_res6"], 6),
            (SAN_FRANCISCO["h3_res8"], 8),
        ]:
            db_session.execute(text("""
                INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, first_visited_at, last_visited_at, visit_count)
                VALUES (:h3_index, :res, :country_id, :state_id,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), NOW(), NOW(), 1)
                ON CONFLICT (h3_index) DO NOTHING
            """), {
                "h3_index": h3_index,
                "res": res,
                "country_id": test_country_usa.id,
                "state_id": test_state_california.id,
                "lon": SAN_FRANCISCO["longitude"],
                "lat": SAN_FRANCISCO["latitude"],
            })
            db_session.execute(text("""
                INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
                VALUES (:user_id, :h3_index, :res, NOW(), NOW(), 1)
                ON CONFLICT (user_id, h3_index) DO NOTHING
            """), {"user_id": test_user.id, "h3_index": h3_index, "res": res})
        db_session.commit()

        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/cells",
            params={
                "min_lng": -123,
                "min_lat": 37,
                "max_lng": -122,
                "max_lat": 38,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["res6"]) == 1
        assert len(data["res8"]) == 1

    def test_empty_viewport_returns_empty_arrays(
        self, client: TestClient, test_user: User
    ):
        """Test that viewport with no cells returns empty arrays."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/cells",
            params={
                "min_lng": 0,
                "min_lat": 0,
                "max_lng": 1,
                "max_lat": 1,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["res6"] == []
        assert data["res8"] == []


@pytest.mark.integration
class TestMapCountryPolygonsEndpoint:
    """Test GET /api/v1/map/polygons/countries endpoint."""

    def test_unauthenticated_returns_401(self, client: TestClient):
        """Test that unauthenticated request returns 401."""
        response = client.get(
            "/api/v1/map/polygons/countries",
            params={"min_lng": -180, "min_lat": -90, "max_lng": 180, "max_lat": 90},
        )
        assert response.status_code == 401

    def test_authenticated_empty_user_returns_empty_features(
        self, client: TestClient, test_user: User
    ):
        """Test that authenticated user with no visits gets empty features."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/polygons/countries",
            params={"min_lng": -180, "min_lat": -90, "max_lng": 180, "max_lat": 90},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert data["features"] == []

    def test_large_bbox_is_allowed(self, client: TestClient, test_user: User):
        """Test that large bounding boxes are allowed for country view."""
        token = create_jwt_token(test_user.id, test_user.username)

        # This would fail for regular /polygons endpoint but should work here
        response = client.get(
            "/api/v1/map/polygons/countries",
            params={"min_lng": -180, "min_lat": -90, "max_lng": 180, "max_lat": 90},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

    def test_returns_visited_country_geometry(
        self,
        client: TestClient,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that visited country geometry is returned."""
        # Add geometry to test country
        db_session.execute(text("""
            UPDATE regions_country
            SET geom = ST_SetSRID(ST_MakePolygon(ST_GeomFromText(
                'LINESTRING(-125 24, -125 50, -66 50, -66 24, -125 24)'
            )), 4326)
            WHERE id = :country_id
        """), {"country_id": test_country_usa.id})

        # Create visit
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, first_visited_at, last_visited_at, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), NOW(), NOW(), 1)
        """), {
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": SAN_FRANCISCO["longitude"],
            "lat": SAN_FRANCISCO["latitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3_index": SAN_FRANCISCO["h3_res8"]})
        db_session.commit()

        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/polygons/countries",
            params={"min_lng": -180, "min_lat": -90, "max_lng": 180, "max_lat": 90},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 1
        assert data["features"][0]["properties"]["code"] == "US"
        assert data["features"][0]["properties"]["type"] == "country"
        assert data["features"][0]["geometry"] is not None


@pytest.mark.integration
class TestMapStatePolygonsEndpoint:
    """Test GET /api/v1/map/polygons/states endpoint."""

    def test_unauthenticated_returns_401(self, client: TestClient):
        """Test that unauthenticated request returns 401."""
        response = client.get(
            "/api/v1/map/polygons/states",
            params={"min_lng": -180, "min_lat": -90, "max_lng": 180, "max_lat": 90},
        )
        assert response.status_code == 401

    def test_authenticated_empty_user_returns_empty_features(
        self, client: TestClient, test_user: User
    ):
        """Test that authenticated user with no visits gets empty features."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/polygons/states",
            params={"min_lng": -180, "min_lat": -90, "max_lng": 180, "max_lat": 90},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert data["features"] == []

    def test_large_bbox_is_allowed(self, client: TestClient, test_user: User):
        """Test that large bounding boxes are allowed for state view."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/polygons/states",
            params={"min_lng": -180, "min_lat": -90, "max_lng": 180, "max_lat": 90},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

    def test_returns_visited_state_geometry(
        self,
        client: TestClient,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that visited state geometry is returned."""
        # Add geometry to test state
        db_session.execute(text("""
            UPDATE regions_state
            SET geom = ST_SetSRID(ST_MakePolygon(ST_GeomFromText(
                'LINESTRING(-125 32, -125 42, -114 42, -114 32, -125 32)'
            )), 4326)
            WHERE id = :state_id
        """), {"state_id": test_state_california.id})

        # Create visit
        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, first_visited_at, last_visited_at, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), NOW(), NOW(), 1)
        """), {
            "h3_index": SAN_FRANCISCO["h3_res8"],
            "country_id": test_country_usa.id,
            "state_id": test_state_california.id,
            "lon": SAN_FRANCISCO["longitude"],
            "lat": SAN_FRANCISCO["latitude"],
        })
        db_session.execute(text("""
            INSERT INTO user_cell_visits (user_id, h3_index, res, first_visited_at, last_visited_at, visit_count)
            VALUES (:user_id, :h3_index, 8, NOW(), NOW(), 1)
        """), {"user_id": test_user.id, "h3_index": SAN_FRANCISCO["h3_res8"]})
        db_session.commit()

        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/map/polygons/states",
            params={"min_lng": -180, "min_lat": -90, "max_lng": 180, "max_lat": 90},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 1
        assert data["features"][0]["properties"]["code"] == "US-CA"
        assert data["features"][0]["properties"]["type"] == "state"
        assert data["features"][0]["geometry"] is not None
