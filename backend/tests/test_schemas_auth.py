import pytest
from pydantic import ValidationError
from schemas.auth import AccountDeleteRequest


def test_account_delete_request_valid():
    """Test valid account deletion request."""
    request = AccountDeleteRequest(
        password="MyPassword123",
        confirmation="DELETE"
    )
    assert request.password == "MyPassword123"
    assert request.confirmation == "DELETE"


def test_account_delete_request_wrong_confirmation():
    """Test that confirmation must be exactly 'DELETE'."""
    with pytest.raises(ValidationError) as exc_info:
        AccountDeleteRequest(
            password="MyPassword123",
            confirmation="delete"  # lowercase should fail
        )

    errors = exc_info.value.errors()
    assert any(
        "Confirmation must be exactly 'DELETE'" in str(error.get("msg", ""))
        for error in errors
    )


def test_account_delete_request_missing_confirmation():
    """Test that confirmation field is required."""
    with pytest.raises(ValidationError):
        AccountDeleteRequest(password="MyPassword123")


def test_account_delete_request_missing_password():
    """Test that password field is required."""
    with pytest.raises(ValidationError):
        AccountDeleteRequest(confirmation="DELETE")
