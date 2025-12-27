"""Shared pytest fixtures for location ingestion tests.

Provides database fixtures, test users, mock data, and helper utilities
for both unit and integration tests.
"""

import os
from datetime import datetime, timedelta
from typing import Generator, Optional
from unittest.mock import MagicMock, Mock

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from database import Base, get_db
from models.device import Device
from models.geo import CountryRegion, StateRegion
from models.user import User
from tests.fixtures.test_data import SAN_FRANCISCO, TOKYO


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Get test database URL from environment or use default.

    For integration tests, you should have a separate test database
    to avoid interfering with development data.
    """
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg2://appuser:apppass@localhost:5433/appdb_test"
    )


@pytest.fixture(scope="session")
def test_engine(test_database_url: str):
    """Create SQLAlchemy engine for test database."""
    engine = create_engine(test_database_url)

    # Create all tables (for integration tests)
    Base.metadata.create_all(bind=engine)

    yield engine

    # Cleanup: drop all tables after test session
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    """Create a database session for integration tests.

    Each test gets a fresh transaction that is rolled back after the test,
    ensuring no test data persists between tests.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    # Rollback transaction and close connection
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def mock_db_session() -> MagicMock:
    """Create a mocked database session for unit tests.

    Returns a MagicMock that can be configured to simulate database
    responses without touching a real database.
    """
    mock_session = MagicMock(spec=Session)

    # Configure common mock responses
    mock_session.commit.return_value = None
    mock_session.rollback.return_value = None
    mock_session.add.return_value = None

    return mock_session


# ============================================================================
# User & Device Fixtures
# ============================================================================

@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user for integration tests."""
    user = User(
        id=1,
        username="test_user",
        email="test@example.com",
        hashed_password="$2b$12$hashedpassword",  # bcrypt hash
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user2(db_session: Session) -> User:
    """Create a second test user for multi-user tests."""
    user = User(
        id=2,
        username="test_user2",
        email="test2@example.com",
        hashed_password="$2b$12$hashedpassword2",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_device(db_session: Session, test_user: User) -> Device:
    """Create a test device linked to test_user."""
    device = Device(
        id=1,
        user_id=test_user.id,
        device_uuid="test-device-uuid-1234",
        device_name="Test iPhone",
        platform="iOS",
    )
    db_session.add(device)
    db_session.commit()
    db_session.refresh(device)
    return device


@pytest.fixture
def mock_user() -> User:
    """Create a mock User object for unit tests."""
    user = Mock(spec=User)
    user.id = 1
    user.username = "test_user"
    user.email = "test@example.com"
    return user


# ============================================================================
# Geography Fixtures
# ============================================================================

@pytest.fixture
def test_country_usa(db_session: Session) -> CountryRegion:
    """Create USA country record for integration tests."""
    # Simple polygon covering San Francisco area
    country = db_session.execute(text("""
        INSERT INTO regions_country (name, iso2, iso3, geom)
        VALUES (
            'United States',
            'US',
            'USA',
            ST_GeomFromText('POLYGON((-125 30, -125 50, -115 50, -115 30, -125 30))', 4326)
        )
        RETURNING id, name, iso2, iso3
    """)).fetchone()

    db_session.commit()

    result = CountryRegion()
    result.id = country.id
    result.name = country.name
    result.iso2 = country.iso2
    result.iso3 = country.iso3
    return result


@pytest.fixture
def test_state_california(db_session: Session, test_country_usa: CountryRegion) -> StateRegion:
    """Create California state record for integration tests."""
    state = db_session.execute(text("""
        INSERT INTO regions_state (name, code, country_id, geom)
        VALUES (
            'California',
            'CA',
            :country_id,
            ST_GeomFromText('POLYGON((-125 32, -125 42, -114 42, -114 32, -125 32))', 4326)
        )
        RETURNING id, name, code, country_id
    """), {"country_id": test_country_usa.id}).fetchone()

    db_session.commit()

    result = StateRegion()
    result.id = state.id
    result.name = state.name
    result.code = state.code
    result.country_id = state.country_id
    return result


@pytest.fixture
def test_country_japan(db_session: Session) -> CountryRegion:
    """Create Japan country record for integration tests."""
    country = db_session.execute(text("""
        INSERT INTO regions_country (name, iso2, iso3, geom)
        VALUES (
            'Japan',
            'JP',
            'JPN',
            ST_GeomFromText('POLYGON((135 30, 135 40, 145 40, 145 30, 135 30))', 4326)
        )
        RETURNING id, name, iso2, iso3
    """)).fetchone()

    db_session.commit()

    result = CountryRegion()
    result.id = country.id
    result.name = country.name
    result.iso2 = country.iso2
    result.iso3 = country.iso3
    return result


@pytest.fixture
def mock_country_usa() -> Mock:
    """Create a mock CountryRegion for USA."""
    country = Mock(spec=CountryRegion)
    country.id = 1
    country.name = "United States"
    country.iso2 = "US"
    country.iso3 = "USA"
    return country


@pytest.fixture
def mock_state_california() -> Mock:
    """Create a mock StateRegion for California."""
    state = Mock(spec=StateRegion)
    state.id = 1
    state.name = "California"
    state.code = "CA"
    state.country_id = 1
    return state


# ============================================================================
# Authentication Fixtures
# ============================================================================

@pytest.fixture
def jwt_secret_key() -> str:
    """JWT secret key for test tokens."""
    return "test-secret-key-do-not-use-in-production"


@pytest.fixture
def valid_jwt_token(test_user: User, jwt_secret_key: str) -> str:
    """Create a valid JWT token for test_user."""
    payload = {
        "sub": str(test_user.id),
        "username": test_user.username,
        "exp": datetime.utcnow() + timedelta(hours=1),
    }
    return jwt.encode(payload, jwt_secret_key, algorithm="HS256")


@pytest.fixture
def expired_jwt_token(test_user: User, jwt_secret_key: str) -> str:
    """Create an expired JWT token."""
    payload = {
        "sub": str(test_user.id),
        "username": test_user.username,
        "exp": datetime.utcnow() - timedelta(hours=1),  # Expired
    }
    return jwt.encode(payload, jwt_secret_key, algorithm="HS256")


# ============================================================================
# FastAPI Test Client
# ============================================================================

@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Create FastAPI test client with overridden database dependency.

    This client uses the test database session instead of the production one.
    """
    # Import app here to avoid loading it for unit tests
    from main import app

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Clean up
    app.dependency_overrides.clear()


# ============================================================================
# Helper Functions
# ============================================================================

def create_jwt_token(user_id: int, username: str, secret_key: str = "test-secret-key") -> str:
    """Helper to create JWT tokens for authentication tests."""
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.utcnow() + timedelta(hours=1),
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def assert_discovery_response(
    response_data: dict,
    expected_new_country: Optional[str] = None,
    expected_new_state: Optional[str] = None,
    expected_new_cells_res6: int = 0,
    expected_new_cells_res8: int = 0,
    expected_revisit_cells_res6: int = 0,
    expected_revisit_cells_res8: int = 0,
):
    """Helper to validate LocationIngestResponse structure and values."""
    assert "discoveries" in response_data
    assert "revisits" in response_data
    assert "visit_counts" in response_data

    discoveries = response_data["discoveries"]
    revisits = response_data["revisits"]
    visit_counts = response_data["visit_counts"]

    # Check country discovery
    if expected_new_country:
        assert discoveries["new_country"] is not None
        assert discoveries["new_country"]["name"] == expected_new_country
    else:
        assert discoveries["new_country"] is None

    # Check state discovery
    if expected_new_state:
        assert discoveries["new_state"] is not None
        assert discoveries["new_state"]["name"] == expected_new_state
    else:
        assert discoveries["new_state"] is None

    # Check cell counts
    assert len(discoveries["new_cells_res6"]) == expected_new_cells_res6
    assert len(discoveries["new_cells_res8"]) == expected_new_cells_res8
    assert len(revisits["cells_res6"]) == expected_revisit_cells_res6
    assert len(revisits["cells_res8"]) == expected_revisit_cells_res8

    # Check visit counts exist
    assert "res6_visit_count" in visit_counts
    assert "res8_visit_count" in visit_counts
