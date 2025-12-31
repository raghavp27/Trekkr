"""Integration tests for DELETE /api/auth/account endpoint."""

import json

import pytest
from fastapi import status
from models.user import User
from models.device import Device
from models.visits import UserCellVisit, IngestBatch
from models.achievements import UserAchievement, Achievement
from models.geo import H3Cell


def test_delete_account_success(client, test_user, auth_headers, db_session):
    """Test successful account deletion with valid password and confirmation."""
    response = client.request(
        "DELETE",
        "/api/auth/account",
        content=json.dumps({"password": "TestPass123", "confirmation": "DELETE"}),
        headers={**auth_headers, "Content-Type": "application/json"},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.content == b""  # No response body for 204

    # Verify token is now invalid (user deleted)
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_delete_account_wrong_password(client, test_user, auth_headers, db_session):
    """Test deletion fails with incorrect password."""
    response = client.request(
        "DELETE",
        "/api/auth/account",
        content=json.dumps({"password": "WrongPassword123", "confirmation": "DELETE"}),
        headers={**auth_headers, "Content-Type": "application/json"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid password" in response.json()["detail"]

    # Verify user still exists
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK


def test_delete_account_unauthenticated(client):
    """Test deletion requires authentication."""
    response = client.request(
        "DELETE",
        "/api/auth/account",
        content=json.dumps({"password": "TestPass123", "confirmation": "DELETE"}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_delete_account_wrong_confirmation(client, test_user, auth_headers):
    """Test deletion fails with incorrect confirmation text."""
    response = client.request(
        "DELETE",
        "/api/auth/account",
        content=json.dumps({"password": "TestPass123", "confirmation": "delete"}),  # lowercase
        headers={**auth_headers, "Content-Type": "application/json"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Verify error message mentions confirmation validation
    errors = response.json()["detail"]
    assert any(
        "Confirmation must be exactly 'DELETE'" in str(error)
        for error in errors
    )

    # Verify user still exists
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK


def test_delete_account_missing_confirmation(client, test_user, auth_headers):
    """Test deletion fails with missing confirmation field."""
    response = client.request(
        "DELETE",
        "/api/auth/account",
        content=json.dumps({"password": "TestPass123"}),
        headers={**auth_headers, "Content-Type": "application/json"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Verify user still exists
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK


def test_delete_account_missing_password(client, test_user, auth_headers):
    """Test deletion fails with missing password field."""
    response = client.request(
        "DELETE",
        "/api/auth/account",
        content=json.dumps({"confirmation": "DELETE"}),
        headers={**auth_headers, "Content-Type": "application/json"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Verify user still exists
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK


def test_delete_account_cascades_to_device(client, test_user, auth_headers, db_session):
    """Test that deleting user cascades to Device table."""
    # Create device for user
    device = Device(
        user_id=test_user.id,
        device_name="Test Device",
        platform="ios"
    )
    db_session.add(device)
    db_session.commit()
    device_id = device.id

    # Verify device exists
    assert db_session.query(Device).filter(Device.id == device_id).count() == 1

    # Expire session to let database CASCADE handle deletion
    db_session.expire_all()

    # Delete account
    response = client.request(
        "DELETE",
        "/api/auth/account",
        content=json.dumps({"password": "TestPass123", "confirmation": "DELETE"}),
        headers={**auth_headers, "Content-Type": "application/json"},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify device was CASCADE deleted
    assert db_session.query(Device).filter(Device.id == device_id).count() == 0
    assert db_session.query(Device).filter(Device.user_id == test_user.id).count() == 0


def test_delete_account_cascades_to_user_cell_visits(client, test_user, auth_headers, db_session):
    """Test that deleting user cascades to UserCellVisit table."""
    # Create H3 cell and user visit
    h3_cell = H3Cell(
        h3_index="882830810ffffff",
        res=8,
        centroid="POINT(-122.4194 37.7749)"
    )
    db_session.add(h3_cell)
    db_session.flush()

    visit = UserCellVisit(
        user_id=test_user.id,
        h3_index="882830810ffffff",
        res=8
    )
    db_session.add(visit)
    db_session.commit()
    visit_id = visit.id

    # Verify visit exists
    assert db_session.query(UserCellVisit).filter(UserCellVisit.id == visit_id).count() == 1

    # Expire session to let database CASCADE handle deletion
    db_session.expire_all()

    # Delete account
    response = client.request(
        "DELETE",
        "/api/auth/account",
        content=json.dumps({"password": "TestPass123", "confirmation": "DELETE"}),
        headers={**auth_headers, "Content-Type": "application/json"},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify visit was CASCADE deleted
    assert db_session.query(UserCellVisit).filter(UserCellVisit.id == visit_id).count() == 0
    assert db_session.query(UserCellVisit).filter(UserCellVisit.user_id == test_user.id).count() == 0


def test_delete_account_cascades_to_ingest_batches(client, test_user, auth_headers, db_session):
    """Test that deleting user cascades to IngestBatch table."""
    # Create ingest batch
    batch = IngestBatch(
        user_id=test_user.id,
        cells_count=50,
        res_min=6,
        res_max=8
    )
    db_session.add(batch)
    db_session.commit()
    batch_id = batch.id

    # Verify batch exists
    assert db_session.query(IngestBatch).filter(IngestBatch.id == batch_id).count() == 1

    # Expire session to let database CASCADE handle deletion
    db_session.expire_all()

    # Delete account
    response = client.request(
        "DELETE",
        "/api/auth/account",
        content=json.dumps({"password": "TestPass123", "confirmation": "DELETE"}),
        headers={**auth_headers, "Content-Type": "application/json"},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify batch was CASCADE deleted
    assert db_session.query(IngestBatch).filter(IngestBatch.id == batch_id).count() == 0
    assert db_session.query(IngestBatch).filter(IngestBatch.user_id == test_user.id).count() == 0


def test_delete_account_cascades_to_user_achievements(client, test_user, auth_headers, db_session):
    """Test that deleting user cascades to UserAchievement table."""
    # Create achievement and user unlock
    achievement = Achievement(
        code="first_steps",
        name="First Steps",
        description="Visit your first location"
    )
    db_session.add(achievement)
    db_session.flush()

    user_achievement = UserAchievement(
        user_id=test_user.id,
        achievement_id=achievement.id
    )
    db_session.add(user_achievement)
    db_session.commit()
    user_achievement_id = user_achievement.id

    # Verify user achievement exists
    assert db_session.query(UserAchievement).filter(UserAchievement.id == user_achievement_id).count() == 1

    # Expire session to let database CASCADE handle deletion
    db_session.expire_all()

    # Delete account
    response = client.request(
        "DELETE",
        "/api/auth/account",
        content=json.dumps({"password": "TestPass123", "confirmation": "DELETE"}),
        headers={**auth_headers, "Content-Type": "application/json"},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify user achievement was CASCADE deleted
    assert db_session.query(UserAchievement).filter(UserAchievement.id == user_achievement_id).count() == 0
    assert db_session.query(UserAchievement).filter(UserAchievement.user_id == test_user.id).count() == 0

    # Verify achievement definition still exists (global catalog)
    assert db_session.query(Achievement).filter(Achievement.id == achievement.id).count() == 1


def test_delete_account_preserves_h3_cells(client, test_user, auth_headers, db_session):
    """Test that deleting user does NOT delete global H3 cells."""
    # Create H3 cell
    h3_cell = H3Cell(
        h3_index="882830810ffffff",
        res=8,
        centroid="POINT(-122.4194 37.7749)"
    )
    db_session.add(h3_cell)
    db_session.flush()

    # Create user visit to that cell
    visit = UserCellVisit(
        user_id=test_user.id,
        h3_index="882830810ffffff",
        res=8
    )
    db_session.add(visit)
    db_session.commit()

    # Verify both cell and visit exist
    assert db_session.query(H3Cell).filter(H3Cell.h3_index == "882830810ffffff").count() == 1
    assert db_session.query(UserCellVisit).filter(UserCellVisit.user_id == test_user.id).count() == 1

    # Expire session to let database CASCADE handle deletion
    db_session.expire_all()

    # Delete account
    response = client.request(
        "DELETE",
        "/api/auth/account",
        content=json.dumps({"password": "TestPass123", "confirmation": "DELETE"}),
        headers={**auth_headers, "Content-Type": "application/json"},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify H3 cell still exists (global registry)
    assert db_session.query(H3Cell).filter(H3Cell.h3_index == "882830810ffffff").count() == 1

    # But user visit is gone
    assert db_session.query(UserCellVisit).filter(UserCellVisit.user_id == test_user.id).count() == 0
