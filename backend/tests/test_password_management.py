"""Tests for password management functionality."""

import hashlib
import os
from unittest.mock import MagicMock, patch

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from models.password_reset import PasswordResetToken
from models.user import User
from schemas.auth import ChangePasswordRequest, ResetPasswordRequest
from services.auth import create_tokens
from services.auth import hash_password, verify_password
from services.password_service import PasswordService


@pytest.mark.integration
class TestUserTokenVersion:
    """Test User model token_version field."""

    def test_user_has_token_version_field(self, db_session: Session):
        """Verify User model has token_version field with default value 1."""
        user = User(
            username="version_test_user",
            email="version@example.com",
            hashed_password="$2b$12$hashedpassword",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert hasattr(user, "token_version")
        assert user.token_version == 1

    def test_token_version_can_be_incremented(self, db_session: Session):
        """Verify token_version can be incremented."""
        user = User(
            username="increment_test_user",
            email="increment@example.com",
            hashed_password="$2b$12$hashedpassword",
        )
        db_session.add(user)
        db_session.commit()

        user.token_version += 1
        db_session.commit()
        db_session.refresh(user)

        assert user.token_version == 2


@pytest.mark.integration
class TestPasswordResetTokenModel:
    """Test PasswordResetToken model."""

    def test_create_password_reset_token(self, db_session: Session, test_user: User):
        """Verify PasswordResetToken can be created and saved."""
        token = PasswordResetToken(
            user_id=test_user.id,
            token_hash="a" * 64,  # SHA-256 hash is 64 hex chars
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db_session.add(token)
        db_session.commit()
        db_session.refresh(token)

        assert token.id is not None
        assert token.user_id == test_user.id
        assert token.token_hash == "a" * 64
        assert token.used_at is None
        assert token.created_at is not None

    def test_token_used_at_tracks_usage(self, db_session: Session, test_user: User):
        """Verify used_at can be set when token is consumed."""
        token = PasswordResetToken(
            user_id=test_user.id,
            token_hash="b" * 64,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db_session.add(token)
        db_session.commit()

        # Mark as used
        token.used_at = datetime.utcnow()
        db_session.commit()
        db_session.refresh(token)

        assert token.used_at is not None

    def test_token_cascade_deletes_with_user(self, db_session: Session):
        """Verify tokens are deleted when user is deleted."""
        # Create user
        user = User(
            username="cascade_test_user",
            email="cascade@example.com",
            hashed_password="$2b$12$hashedpassword",
        )
        db_session.add(user)
        db_session.commit()

        # Create token for user
        token = PasswordResetToken(
            user_id=user.id,
            token_hash="c" * 64,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db_session.add(token)
        db_session.commit()
        token_id = token.id

        # Delete user
        db_session.delete(user)
        db_session.commit()

        # Verify token is gone
        deleted_token = (
            db_session.query(PasswordResetToken)
            .filter(PasswordResetToken.id == token_id)
            .first()
        )
        assert deleted_token is None


class TestPasswordSchemas:
    """Test password management Pydantic schemas."""

    def test_change_password_request_valid(self):
        """Verify valid change password request passes validation."""
        request = ChangePasswordRequest(
            current_password="OldPass123",
            new_password="NewPass456",
        )
        assert request.current_password == "OldPass123"
        assert request.new_password == "NewPass456"

    def test_change_password_request_weak_password_rejected(self):
        """Verify weak new password is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ChangePasswordRequest(
                current_password="OldPass123",
                new_password="weak",
            )
        assert "at least 8 characters" in str(exc_info.value)

    def test_change_password_request_no_uppercase_rejected(self):
        """Verify password without uppercase is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ChangePasswordRequest(
                current_password="OldPass123",
                new_password="newpass123",
            )
        assert "uppercase" in str(exc_info.value)

    def test_change_password_request_no_lowercase_rejected(self):
        """Verify password without lowercase is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ChangePasswordRequest(
                current_password="OldPass123",
                new_password="NEWPASS123",
            )
        assert "lowercase" in str(exc_info.value)

    def test_change_password_request_no_number_rejected(self):
        """Verify password without number is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ChangePasswordRequest(
                current_password="OldPass123",
                new_password="NewPassWord",
            )
        assert "number" in str(exc_info.value)

    def test_reset_password_request_valid(self):
        """Verify valid reset password request passes validation."""
        request = ResetPasswordRequest(
            token="some_reset_token",
            new_password="NewPass789",
        )
        assert request.token == "some_reset_token"
        assert request.new_password == "NewPass789"

    def test_reset_password_request_weak_password_rejected(self):
        """Verify weak password in reset request is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ResetPasswordRequest(
                token="some_reset_token",
                new_password="weak",
            )
        assert "at least 8 characters" in str(exc_info.value)


@pytest.mark.integration
class TestTokenVersionValidation:
    """Test token version validation in auth service."""

    def test_token_includes_version(self, db_session: Session, test_user: User):
        """Verify created tokens include token_ver claim."""
        from jose import jwt

        # Ensure user has token_version
        test_user.token_version = 1
        db_session.commit()

        tokens = create_tokens(test_user)

        # Decode and check
        payload = jwt.decode(
            tokens["access_token"],
            "test-secret-key",
            algorithms=["HS256"],
        )

        assert "token_ver" in payload
        assert payload["token_ver"] == 1

    def test_mismatched_token_version_rejected(
        self,
        client,
        db_session: Session,
        test_user: User,
    ):
        """Verify token with old version is rejected after increment."""
        from jose import jwt

        # User starts with token_version = 1 (set by fixture or default)
        test_user.token_version = 1
        db_session.commit()

        # Create token with version 1
        payload = {
            "sub": str(test_user.id),
            "username": test_user.username,
            "exp": datetime.utcnow() + timedelta(hours=1),
            "type": "access",
            "token_ver": 1,
        }
        old_token = jwt.encode(payload, "test-secret-key", algorithm="HS256")

        # Increment user's token version (simulating password change)
        test_user.token_version = 2
        db_session.commit()

        # Try to use old token
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {old_token}"},
        )

        assert response.status_code == 401
        assert (
            "invalidated" in response.json()["detail"].lower()
            or "log in again" in response.json()["detail"].lower()
        )


@pytest.mark.integration
class TestPasswordServiceChangePassword:
    """Test PasswordService.change_password method."""

    def test_change_password_success(self, db_session: Session):
        """Verify password can be changed with correct current password."""
        # Create user with known password
        original_password = "OriginalPass123"
        user = User(
            username="change_pass_user",
            email="changepass@example.com",
            hashed_password=hash_password(original_password),
            token_version=1,
        )
        db_session.add(user)
        db_session.commit()

        # Change password
        service = PasswordService(db_session)
        result = service.change_password(
            user=user,
            current_password=original_password,
            new_password="NewPassword456",
        )

        assert result is True

        # Verify new password works
        db_session.refresh(user)
        assert verify_password("NewPassword456", user.hashed_password)

        # Verify token version was incremented
        assert user.token_version == 2

    def test_change_password_wrong_current_password(self, db_session: Session):
        """Verify change fails with incorrect current password."""
        user = User(
            username="wrong_pass_user",
            email="wrongpass@example.com",
            hashed_password=hash_password("CorrectPass123"),
            token_version=1,
        )
        db_session.add(user)
        db_session.commit()

        service = PasswordService(db_session)
        result = service.change_password(
            user=user,
            current_password="WrongPass123",
            new_password="NewPassword456",
        )

        assert result is False

        # Verify password unchanged
        db_session.refresh(user)
        assert verify_password("CorrectPass123", user.hashed_password)

        # Verify token version unchanged
        assert user.token_version == 1


class TestEmailService:
    """Test EmailService for password reset emails."""

    @patch("services.email_service.SendGridAPIClient")
    def test_send_password_reset_success(self, mock_sendgrid_class):
        """Verify password reset email is sent via SendGrid."""
        from services.email_service import EmailService

        # Configure mock
        mock_client = MagicMock()
        mock_sendgrid_class.return_value = mock_client
        mock_client.send.return_value = MagicMock(status_code=202)

        # Send email
        service = EmailService()
        result = service.send_password_reset(
            to_email="user@example.com",
            username="testuser",
            token="test_token_123",
        )

        assert result is True
        mock_client.send.assert_called_once()

    @patch("services.email_service.SendGridAPIClient")
    def test_send_password_reset_failure_returns_false(self, mock_sendgrid_class):
        """Verify failed email send returns False."""
        from services.email_service import EmailService

        # Configure mock to raise exception
        mock_client = MagicMock()
        mock_sendgrid_class.return_value = mock_client
        mock_client.send.side_effect = Exception("SendGrid error")

        service = EmailService()
        result = service.send_password_reset(
            to_email="user@example.com",
            username="testuser",
            token="test_token_123",
        )

        assert result is False

    def test_email_contains_reset_url(self):
        """Verify email HTML contains reset URL with token."""
        from services.email_service import EmailService

        os.environ["FRONTEND_URL"] = "https://trekkr.app"

        service = EmailService()
        html = service._build_reset_email_html(
            username="testuser",
            reset_url="https://trekkr.app/reset-password?token=abc123",
        )

        assert "https://trekkr.app/reset-password?token=abc123" in html
        assert "testuser" in html
        assert "Reset Password" in html


@pytest.mark.integration
class TestPasswordServiceForgotPassword:
    """Test PasswordService.request_password_reset method."""

    @patch("services.password_service.EmailService")
    def test_request_reset_creates_token(
        self,
        mock_email_class,
        db_session: Session,
    ):
        """Verify reset request creates token and sends email."""
        mock_email_instance = MagicMock()
        mock_email_class.return_value = mock_email_instance
        mock_email_instance.send_password_reset.return_value = True

        # Create user
        user = User(
            username="forgot_user",
            email="forgot@example.com",
            hashed_password=hash_password("SomePass123"),
            token_version=1,
        )
        db_session.add(user)
        db_session.commit()

        # Request reset
        service = PasswordService(db_session)
        service.request_password_reset("forgot@example.com")

        # Verify token was created
        token = (
            db_session.query(PasswordResetToken)
            .filter(PasswordResetToken.user_id == user.id)
            .first()
        )

        assert token is not None
        assert token.used_at is None
        assert token.expires_at > datetime.utcnow()

        # Verify email was sent
        mock_email_instance.send_password_reset.assert_called_once()
        call_args = mock_email_instance.send_password_reset.call_args
        assert call_args[1]["to_email"] == "forgot@example.com"
        assert call_args[1]["username"] == "forgot_user"

    @patch("services.password_service.EmailService")
    def test_request_reset_nonexistent_email_silent(
        self,
        mock_email_class,
        db_session: Session,
    ):
        """Verify no error for non-existent email (prevents enumeration)."""
        mock_email_instance = MagicMock()
        mock_email_class.return_value = mock_email_instance

        service = PasswordService(db_session)

        # Should not raise
        service.request_password_reset("nobody@example.com")

        # Verify no email was sent
        mock_email_instance.send_password_reset.assert_not_called()

    @patch("services.password_service.EmailService")
    def test_request_reset_invalidates_old_tokens(
        self,
        mock_email_class,
        db_session: Session,
    ):
        """Verify new request invalidates previous unused tokens."""
        mock_email_instance = MagicMock()
        mock_email_class.return_value = mock_email_instance
        mock_email_instance.send_password_reset.return_value = True

        # Create user
        user = User(
            username="multi_reset_user",
            email="multireset@example.com",
            hashed_password=hash_password("SomePass123"),
            token_version=1,
        )
        db_session.add(user)
        db_session.commit()

        service = PasswordService(db_session)

        # First request
        service.request_password_reset("multireset@example.com")

        # Second request
        service.request_password_reset("multireset@example.com")

        # Should only have one active token
        tokens = (
            db_session.query(PasswordResetToken)
            .filter(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
            .all()
        )

        assert len(tokens) == 1


@pytest.mark.integration
class TestPasswordServiceResetPassword:
    """Test PasswordService.reset_password method."""

    def test_reset_password_success(self, db_session: Session):
        """Verify password reset with valid token."""
        # Create user
        user = User(
            username="reset_user",
            email="reset@example.com",
            hashed_password=hash_password("OldPass123"),
            token_version=1,
        )
        db_session.add(user)
        db_session.commit()

        # Create valid token
        raw_token = "test_reset_token_12345"
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db_session.add(reset_token)
        db_session.commit()

        # Reset password
        service = PasswordService(db_session)
        result = service.reset_password(
            raw_token=raw_token,
            new_password="NewPassword789",
        )

        assert result is True

        # Verify new password works
        db_session.refresh(user)
        assert verify_password("NewPassword789", user.hashed_password)

        # Verify token version incremented
        assert user.token_version == 2

        # Verify token marked as used
        db_session.refresh(reset_token)
        assert reset_token.used_at is not None

    def test_reset_password_invalid_token(self, db_session: Session):
        """Verify reset fails with invalid token."""
        service = PasswordService(db_session)
        result = service.reset_password(
            raw_token="completely_invalid_token",
            new_password="NewPassword789",
        )

        assert result is False

    def test_reset_password_expired_token(self, db_session: Session):
        """Verify reset fails with expired token."""
        # Create user
        user = User(
            username="expired_user",
            email="expired@example.com",
            hashed_password=hash_password("OldPass123"),
            token_version=1,
        )
        db_session.add(user)
        db_session.commit()

        # Create expired token
        raw_token = "expired_token_12345"
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Already expired
        )
        db_session.add(reset_token)
        db_session.commit()

        # Try to reset
        service = PasswordService(db_session)
        result = service.reset_password(
            raw_token=raw_token,
            new_password="NewPassword789",
        )

        assert result is False

    def test_reset_password_already_used_token(self, db_session: Session):
        """Verify reset fails with already-used token."""
        # Create user
        user = User(
            username="used_token_user",
            email="usedtoken@example.com",
            hashed_password=hash_password("OldPass123"),
            token_version=1,
        )
        db_session.add(user)
        db_session.commit()

        # Create already-used token
        raw_token = "used_token_12345"
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(hours=1),
            used_at=datetime.utcnow() - timedelta(minutes=30),  # Already used
        )
        db_session.add(reset_token)
        db_session.commit()

        # Try to reset
        service = PasswordService(db_session)
        result = service.reset_password(
            raw_token=raw_token,
            new_password="NewPassword789",
        )

        assert result is False


@pytest.mark.integration
class TestChangePasswordEndpoint:
    """Test POST /api/auth/change-password endpoint."""

    def test_change_password_success(
        self,
        client: TestClient,
        db_session: Session,
    ):
        """Verify password change with valid credentials."""
        # Create user with known password
        original_password = "OriginalPass123"
        user = User(
            username="endpoint_user",
            email="endpoint@example.com",
            hashed_password=hash_password(original_password),
            token_version=1,
        )
        db_session.add(user)
        db_session.commit()

        # Get valid token
        from jose import jwt

        token_payload = {
            "sub": str(user.id),
            "type": "access",
            "token_ver": 1,
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        token = jwt.encode(token_payload, "test-secret-key", algorithm="HS256")

        # Change password
        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": original_password,
                "new_password": "NewPassword456",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert "successfully" in response.json()["message"].lower()

    def test_change_password_wrong_current(
        self,
        client: TestClient,
        db_session: Session,
    ):
        """Verify rejection with wrong current password."""
        user = User(
            username="wrong_current_user",
            email="wrongcurrent@example.com",
            hashed_password=hash_password("CorrectPass123"),
            token_version=1,
        )
        db_session.add(user)
        db_session.commit()

        from jose import jwt

        token_payload = {
            "sub": str(user.id),
            "type": "access",
            "token_ver": 1,
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        token = jwt.encode(token_payload, "test-secret-key", algorithm="HS256")

        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "WrongPass123",
                "new_password": "NewPassword456",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401

    def test_change_password_unauthenticated(self, client: TestClient):
        """Verify endpoint requires authentication."""
        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "OldPass123",
                "new_password": "NewPass456",
            },
        )

        assert response.status_code == 401

    def test_change_password_weak_password_rejected(
        self,
        client: TestClient,
        db_session: Session,
    ):
        """Verify weak new password is rejected with 422."""
        user = User(
            username="weak_pass_user",
            email="weakpass@example.com",
            hashed_password=hash_password("CorrectPass123"),
            token_version=1,
        )
        db_session.add(user)
        db_session.commit()

        from jose import jwt

        token_payload = {
            "sub": str(user.id),
            "type": "access",
            "token_ver": 1,
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        token = jwt.encode(token_payload, "test-secret-key", algorithm="HS256")

        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "CorrectPass123",
                "new_password": "weak",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422

    def test_change_password_invalidates_old_token(
        self,
        client: TestClient,
        db_session: Session,
    ):
        """Verify old token stops working after password change."""
        user = User(
            username="invalidate_user",
            email="invalidate@example.com",
            hashed_password=hash_password("OriginalPass123"),
            token_version=1,
        )
        db_session.add(user)
        db_session.commit()

        from jose import jwt

        token_payload = {
            "sub": str(user.id),
            "type": "access",
            "token_ver": 1,
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        old_token = jwt.encode(token_payload, "test-secret-key", algorithm="HS256")

        # Change password
        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "OriginalPass123",
                "new_password": "NewPassword456",
            },
            headers={"Authorization": f"Bearer {old_token}"},
        )
        assert response.status_code == 200

        # Try to use old token
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {old_token}"},
        )

        assert response.status_code == 401


@pytest.mark.integration
class TestForgotPasswordEndpoint:
    """Test POST /api/auth/forgot-password endpoint."""

    @patch("services.password_service.EmailService")
    def test_forgot_password_existing_email(
        self,
        mock_email_class,
        client: TestClient,
        db_session: Session,
    ):
        """Verify reset email sent for existing user."""
        mock_email_instance = MagicMock()
        mock_email_class.return_value = mock_email_instance
        mock_email_instance.send_password_reset.return_value = True

        user = User(
            username="forgot_endpoint_user",
            email="forgotendpoint@example.com",
            hashed_password=hash_password("SomePass123"),
            token_version=1,
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/auth/forgot-password",
            json={"email": "forgotendpoint@example.com"},
        )

        assert response.status_code == 200
        assert "password reset link" in response.json()["message"].lower()

    @patch("services.password_service.EmailService")
    def test_forgot_password_nonexistent_email_same_response(
        self,
        mock_email_class,
        client: TestClient,
    ):
        """Verify same response for non-existent email (no enumeration)."""
        response = client.post(
            "/api/auth/forgot-password",
            json={"email": "nonexistent@example.com"},
        )

        # Should return 200 with same message
        assert response.status_code == 200
        assert "password reset link" in response.json()["message"].lower()

    def test_forgot_password_invalid_email_format(self, client: TestClient):
        """Verify invalid email format is rejected."""
        response = client.post(
            "/api/auth/forgot-password",
            json={"email": "not-an-email"},
        )

        assert response.status_code == 422


@pytest.mark.integration
class TestResetPasswordEndpoint:
    """Test POST /api/auth/reset-password endpoint."""

    def test_reset_password_success(
        self,
        client: TestClient,
        db_session: Session,
    ):
        """Verify password reset with valid token."""
        user = User(
            username="reset_endpoint_user",
            email="resetendpoint@example.com",
            hashed_password=hash_password("OldPass123"),
            token_version=1,
        )
        db_session.add(user)
        db_session.commit()

        # Create valid token
        raw_token = "endpoint_reset_token_12345"
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db_session.add(reset_token)
        db_session.commit()

        response = client.post(
            "/api/auth/reset-password",
            json={
                "token": raw_token,
                "new_password": "NewPassword789",
            },
        )

        assert response.status_code == 200
        assert "successfully" in response.json()["message"].lower()

    def test_reset_password_invalid_token(self, client: TestClient):
        """Verify reset fails with invalid token."""
        response = client.post(
            "/api/auth/reset-password",
            json={
                "token": "totally_invalid_token",
                "new_password": "NewPassword789",
            },
        )

        assert response.status_code == 400

    def test_reset_password_expired_token(
        self,
        client: TestClient,
        db_session: Session,
    ):
        """Verify reset fails with expired token."""
        user = User(
            username="expired_endpoint_user",
            email="expiredendpoint@example.com",
            hashed_password=hash_password("OldPass123"),
            token_version=1,
        )
        db_session.add(user)
        db_session.commit()

        # Create expired token
        raw_token = "expired_endpoint_token"
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        db_session.add(reset_token)
        db_session.commit()

        response = client.post(
            "/api/auth/reset-password",
            json={
                "token": raw_token,
                "new_password": "NewPassword789",
            },
        )

        assert response.status_code == 400

    def test_reset_password_already_used_token(
        self,
        client: TestClient,
        db_session: Session,
    ):
        """Verify reset fails with already-used token."""
        user = User(
            username="used_endpoint_user",
            email="usedendpoint@example.com",
            hashed_password=hash_password("OldPass123"),
            token_version=1,
        )
        db_session.add(user)
        db_session.commit()

        # Create used token
        raw_token = "used_endpoint_token"
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(hours=1),
            used_at=datetime.utcnow() - timedelta(minutes=30),
        )
        db_session.add(reset_token)
        db_session.commit()

        response = client.post(
            "/api/auth/reset-password",
            json={
                "token": raw_token,
                "new_password": "NewPassword789",
            },
        )

        assert response.status_code == 400

    def test_reset_password_weak_password_rejected(
        self,
        client: TestClient,
        db_session: Session,
    ):
        """Verify weak password is rejected with 422."""
        user = User(
            username="weak_reset_user",
            email="weakreset@example.com",
            hashed_password=hash_password("OldPass123"),
            token_version=1,
        )
        db_session.add(user)
        db_session.commit()

        raw_token = "weak_reset_token"
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db_session.add(reset_token)
        db_session.commit()

        response = client.post(
            "/api/auth/reset-password",
            json={
                "token": raw_token,
                "new_password": "weak",
            },
        )

        assert response.status_code == 422

