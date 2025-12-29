"""Integration tests for stats router endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from models.user import User
from models.geo import CountryRegion, StateRegion
from tests.conftest import create_jwt_token
from tests.fixtures.test_data import SAN_FRANCISCO
# Verify we can import new response models
from schemas.stats import (
    UserInfoResponse,
    StatsResponse,
    RecentCountryResponse,
    RecentRegionResponse,
    OverviewResponse,
)


@pytest.mark.integration
class TestStatsCountriesEndpoint:
    """Test GET /api/v1/stats/countries endpoint."""

    def test_unauthenticated_returns_401(self, client: TestClient):
        """Test that unauthenticated request returns 401."""
        response = client.get("/api/v1/stats/countries")
        assert response.status_code == 401

    def test_returns_empty_for_new_user(
        self, client: TestClient, test_user: User
    ):
        """Test that new user with no visits gets empty response."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/stats/countries",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_countries_visited"] == 0
        assert data["countries"] == []

    def test_returns_country_stats(
        self,
        client: TestClient,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that endpoint returns country statistics."""
        # Set up test data
        db_session.execute(text("""
            UPDATE regions_country SET land_cells_total_resolution8 = 1000 WHERE id = :id
        """), {"id": test_country_usa.id})

        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 1)
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
            "/api/v1/stats/countries",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_countries_visited"] == 1
        assert len(data["countries"]) == 1
        assert data["countries"][0]["code"] == "US"
        assert data["countries"][0]["coverage_pct"] == 0.001

    def test_query_params_work(
        self, client: TestClient, test_user: User
    ):
        """Test that query parameters are accepted."""
        token = create_jwt_token(test_user.id, test_user.username)
        
        response = client.get(
            "/api/v1/stats/countries?sort_by=name&order=asc&limit=10&offset=0",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    def test_invalid_sort_by_returns_422(
        self, client: TestClient, test_user: User
    ):
        """Test that invalid sort_by returns validation error."""
        token = create_jwt_token(test_user.id, test_user.username)
        
        response = client.get(
            "/api/v1/stats/countries?sort_by=invalid",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    def test_limit_over_100_returns_422(
        self, client: TestClient, test_user: User
    ):
        """Test that limit > 100 returns validation error."""
        token = create_jwt_token(test_user.id, test_user.username)
        
        response = client.get(
            "/api/v1/stats/countries?limit=101",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422


@pytest.mark.integration
class TestStatsRegionsEndpoint:
    """Test GET /api/v1/stats/regions endpoint."""

    def test_unauthenticated_returns_401(self, client: TestClient):
        """Test that unauthenticated request returns 401."""
        response = client.get("/api/v1/stats/regions")
        assert response.status_code == 401

    def test_returns_empty_for_new_user(
        self, client: TestClient, test_user: User
    ):
        """Test that new user with no visits gets empty response."""
        token = create_jwt_token(test_user.id, test_user.username)

        response = client.get(
            "/api/v1/stats/regions",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_regions_visited"] == 0
        assert data["regions"] == []

    def test_returns_region_stats(
        self,
        client: TestClient,
        db_session,
        test_user: User,
        test_country_usa: CountryRegion,
        test_state_california: StateRegion,
    ):
        """Test that endpoint returns region statistics."""
        # Set up test data
        db_session.execute(text("""
            UPDATE regions_state SET land_cells_total_resolution8 = 500 WHERE id = :id
        """), {"id": test_state_california.id})

        db_session.execute(text("""
            INSERT INTO h3_cells (h3_index, res, country_id, state_id, centroid, visit_count)
            VALUES (:h3_index, 8, :country_id, :state_id,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 1)
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
            "/api/v1/stats/regions",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_regions_visited"] == 1
        assert len(data["regions"]) == 1
        assert data["regions"][0]["code"] == "US-CA"
        assert data["regions"][0]["name"] == "California"
        assert data["regions"][0]["country_code"] == "US"
        assert data["regions"][0]["coverage_pct"] == 0.002
