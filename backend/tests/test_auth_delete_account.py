"""Integration tests for DELETE /api/auth/account endpoint."""

import json

import pytest
from fastapi import status
from models.user import User


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
