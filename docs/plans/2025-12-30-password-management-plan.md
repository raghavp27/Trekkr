# Password Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement password change, forgot password, and reset password functionality with session invalidation via token versioning.

**Architecture:** Three new endpoints in auth router, a new PasswordService for business logic, EmailService for SendGrid integration, and a PasswordResetToken model for storing hashed reset tokens. Token versioning on User model enables invalidating all sessions on password change.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, SendGrid (email), bcrypt (hashing), pytest

---

## Task 1: Database Migration - Add Token Versioning and Password Reset Tokens

**Files:**
- Create: `backend/alembic/versions/20251230_0010_add_password_management.py`

**Step 1: Create the migration file**

```python
"""Add token versioning and password reset tokens.

Revision ID: 0010
Revises: 0009
Create Date: 2025-12-30
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade():
    # Add token_version to users table for session invalidation
    op.add_column(
        'users',
        sa.Column('token_version', sa.Integer(), nullable=False, server_default='1')
    )

    # Create password_reset_tokens table
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Add indexes
    op.create_index('ix_password_reset_tokens_token_hash', 'password_reset_tokens', ['token_hash'], unique=True)
    op.create_index('ix_password_reset_tokens_user_id', 'password_reset_tokens', ['user_id'])


def downgrade():
    op.drop_index('ix_password_reset_tokens_user_id')
    op.drop_index('ix_password_reset_tokens_token_hash')
    op.drop_table('password_reset_tokens')
    op.drop_column('users', 'token_version')
```

**Step 2: Run migration**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" alembic upgrade head
```

Expected: Migration applies successfully, shows "0009 -> 0010"

**Step 3: Verify migration**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" alembic current
```

Expected: Shows revision `0010`

**Step 4: Commit**

```bash
git add backend/alembic/versions/20251230_0010_add_password_management.py
git commit -m "migration: add token_version and password_reset_tokens table"
```

---

## Task 2: Update User Model with Token Version

**Files:**
- Modify: `backend/models/user.py`

**Step 1: Write the failing test**

Create file `backend/tests/test_password_management.py`:

```python
"""Tests for password management functionality."""

import pytest
from sqlalchemy.orm import Session

from models.user import User


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

        assert hasattr(user, 'token_version')
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
```

**Step 2: Run test to verify it fails**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestUserTokenVersion -v
```

Expected: FAIL - `AttributeError: 'User' object has no attribute 'token_version'`

**Step 3: Update User model**

Modify `backend/models/user.py`:

```python
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    token_version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
```

**Step 4: Run test to verify it passes**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestUserTokenVersion -v
```

Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/models/user.py backend/tests/test_password_management.py
git commit -m "feat: add token_version field to User model"
```

---

## Task 3: Create PasswordResetToken Model

**Files:**
- Create: `backend/models/password_reset.py`
- Modify: `backend/models/__init__.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_password_management.py`:

```python
from datetime import datetime, timedelta

from models.password_reset import PasswordResetToken


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
        deleted_token = db_session.query(PasswordResetToken).filter(
            PasswordResetToken.id == token_id
        ).first()
        assert deleted_token is None
```

**Step 2: Run test to verify it fails**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestPasswordResetTokenModel -v
```

Expected: FAIL - `ModuleNotFoundError: No module named 'models.password_reset'`

**Step 3: Create PasswordResetToken model**

Create file `backend/models/password_reset.py`:

```python
"""Password reset token model for account recovery."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class PasswordResetToken(Base):
    """Stores hashed password reset tokens with expiration."""

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", backref="password_reset_tokens")
```

**Step 4: Update models/__init__.py**

Modify `backend/models/__init__.py`:

```python
"""Model package exports for database initialization."""

from models.user import User
from models.device import Device
from models.geo import CountryRegion, StateRegion, H3Cell
from models.visits import UserCellVisit, IngestBatch
from models.stats import UserCountryStat, UserStateStat, UserStreak
from models.achievements import Achievement, UserAchievement
from models.password_reset import PasswordResetToken

__all__ = [
    "User",
    "Device",
    "CountryRegion",
    "StateRegion",
    "H3Cell",
    "UserCellVisit",
    "IngestBatch",
    "UserCountryStat",
    "UserStateStat",
    "UserStreak",
    "Achievement",
    "UserAchievement",
    "PasswordResetToken",
]
```

**Step 5: Run test to verify it passes**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestPasswordResetTokenModel -v
```

Expected: PASS (3 tests)

**Step 6: Commit**

```bash
git add backend/models/password_reset.py backend/models/__init__.py backend/tests/test_password_management.py
git commit -m "feat: add PasswordResetToken model"
```

---

## Task 4: Add Password Validation Schema

**Files:**
- Modify: `backend/schemas/auth.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_password_management.py`:

```python
import pytest
from pydantic import ValidationError

from schemas.auth import ChangePasswordRequest, ResetPasswordRequest


class TestPasswordSchemas:
    """Test password management Pydantic schemas."""

    def test_change_password_request_valid(self):
        """Verify valid change password request passes validation."""
        request = ChangePasswordRequest(
            current_password="OldPass123",
            new_password="NewPass456"
        )
        assert request.current_password == "OldPass123"
        assert request.new_password == "NewPass456"

    def test_change_password_request_weak_password_rejected(self):
        """Verify weak new password is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ChangePasswordRequest(
                current_password="OldPass123",
                new_password="weak"
            )
        assert "at least 8 characters" in str(exc_info.value)

    def test_change_password_request_no_uppercase_rejected(self):
        """Verify password without uppercase is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ChangePasswordRequest(
                current_password="OldPass123",
                new_password="newpass123"
            )
        assert "uppercase" in str(exc_info.value)

    def test_change_password_request_no_lowercase_rejected(self):
        """Verify password without lowercase is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ChangePasswordRequest(
                current_password="OldPass123",
                new_password="NEWPASS123"
            )
        assert "lowercase" in str(exc_info.value)

    def test_change_password_request_no_number_rejected(self):
        """Verify password without number is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ChangePasswordRequest(
                current_password="OldPass123",
                new_password="NewPassWord"
            )
        assert "number" in str(exc_info.value)

    def test_reset_password_request_valid(self):
        """Verify valid reset password request passes validation."""
        request = ResetPasswordRequest(
            token="some_reset_token",
            new_password="NewPass789"
        )
        assert request.token == "some_reset_token"
        assert request.new_password == "NewPass789"

    def test_reset_password_request_weak_password_rejected(self):
        """Verify weak password in reset request is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ResetPasswordRequest(
                token="some_reset_token",
                new_password="weak"
            )
        assert "at least 8 characters" in str(exc_info.value)
```

**Step 2: Run test to verify it fails**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestPasswordSchemas -v
```

Expected: FAIL - `ImportError: cannot import name 'ChangePasswordRequest' from 'schemas.auth'`

**Step 3: Add schemas to auth.py**

Add to `backend/schemas/auth.py` (after existing imports):

```python
class ChangePasswordRequest(BaseModel):
    """Request schema for changing password."""

    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one number")
        return v


class ForgotPasswordRequest(BaseModel):
    """Request schema for forgot password."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Request schema for resetting password with token."""

    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one number")
        return v
```

**Step 4: Run test to verify it passes**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestPasswordSchemas -v
```

Expected: PASS (7 tests)

**Step 5: Commit**

```bash
git add backend/schemas/auth.py backend/tests/test_password_management.py
git commit -m "feat: add password management request schemas"
```

---

## Task 5: Update Auth Service for Token Versioning

**Files:**
- Modify: `backend/services/auth.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_password_management.py`:

```python
from services.auth import create_tokens, get_current_user
from fastapi import HTTPException


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
            algorithms=["HS256"]
        )

        assert "token_ver" in payload
        assert payload["token_ver"] == 1

    def test_mismatched_token_version_rejected(
        self,
        client,
        db_session: Session,
        test_user: User
    ):
        """Verify token with old version is rejected after increment."""
        from tests.conftest import create_jwt_token
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
            headers={"Authorization": f"Bearer {old_token}"}
        )

        assert response.status_code == 401
        assert "invalidated" in response.json()["detail"].lower() or "log in again" in response.json()["detail"].lower()
```

**Step 2: Run test to verify it fails**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestTokenVersionValidation -v
```

Expected: FAIL - token_ver not in payload or mismatched version not rejected

**Step 3: Update auth service**

Modify `backend/services/auth.py` - update `create_tokens` function:

```python
def create_tokens(user: User) -> dict:
    """Create both access and refresh tokens for a user."""
    # Include token_version in payload for session invalidation
    access_token = create_access_token(data={
        "sub": str(user.id),
        "token_ver": user.token_version
    })
    refresh_token = create_refresh_token(data={
        "sub": str(user.id),
        "token_ver": user.token_version
    })
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
```

Modify `get_current_user` function - add version check after fetching user:

```python
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Get the current authenticated user from the JWT token."""
    payload = decode_token(token)

    # Ensure it's an access token
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == int(user_id_str)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate token version (session invalidation check)
    token_version = payload.get("token_ver")
    if token_version is None or token_version != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalidated. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
```

**Step 4: Run test to verify it passes**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestTokenVersionValidation -v
```

Expected: PASS (2 tests)

**Step 5: Run all existing auth tests to ensure no regression**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_auth_router.py -v
```

Expected: All tests pass (may need to update fixtures to include token_ver)

**Step 6: Commit**

```bash
git add backend/services/auth.py backend/tests/test_password_management.py
git commit -m "feat: add token version validation to auth service"
```

---

## Task 6: Create PasswordService - Change Password

**Files:**
- Create: `backend/services/password_service.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_password_management.py`:

```python
from services.password_service import PasswordService
from services.auth import hash_password, verify_password


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
            new_password="NewPassword456"
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
            new_password="NewPassword456"
        )

        assert result is False

        # Verify password unchanged
        db_session.refresh(user)
        assert verify_password("CorrectPass123", user.hashed_password)

        # Verify token version unchanged
        assert user.token_version == 1
```

**Step 2: Run test to verify it fails**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestPasswordServiceChangePassword -v
```

Expected: FAIL - `ModuleNotFoundError: No module named 'services.password_service'`

**Step 3: Create PasswordService**

Create file `backend/services/password_service.py`:

```python
"""Password management service for change/forgot/reset flows."""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from models.password_reset import PasswordResetToken
from models.user import User
from services.auth import hash_password, verify_password

RESET_TOKEN_EXPIRY_HOURS = 1


class PasswordService:
    """Handles password change, forgot, and reset operations."""

    def __init__(self, db: Session):
        self.db = db

    def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str
    ) -> bool:
        """
        Change password for authenticated user.

        Returns True on success, False if current password is wrong.
        Increments token_version to invalidate all existing sessions.
        """
        # Verify current password
        if not verify_password(current_password, user.hashed_password):
            return False

        # Update password
        user.hashed_password = hash_password(new_password)

        # Invalidate all sessions by incrementing token version
        user.token_version += 1

        self.db.commit()
        return True
```

**Step 4: Run test to verify it passes**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestPasswordServiceChangePassword -v
```

Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/services/password_service.py backend/tests/test_password_management.py
git commit -m "feat: add PasswordService with change_password method"
```

---

## Task 7: Create Email Service

**Files:**
- Create: `backend/services/email_service.py`
- Modify: `backend/config.py`
- Modify: `backend/requirements.txt`

**Step 1: Write the failing test**

Add to `backend/tests/test_password_management.py`:

```python
from unittest.mock import patch, MagicMock


class TestEmailService:
    """Test EmailService for password reset emails."""

    @patch('services.email_service.SendGridAPIClient')
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
            token="test_token_123"
        )

        assert result is True
        mock_client.send.assert_called_once()

    @patch('services.email_service.SendGridAPIClient')
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
            token="test_token_123"
        )

        assert result is False

    def test_email_contains_reset_url(self):
        """Verify email HTML contains reset URL with token."""
        from services.email_service import EmailService
        import os

        os.environ["FRONTEND_URL"] = "https://trekkr.app"

        service = EmailService()
        html = service._build_reset_email_html(
            username="testuser",
            reset_url="https://trekkr.app/reset-password?token=abc123"
        )

        assert "https://trekkr.app/reset-password?token=abc123" in html
        assert "testuser" in html
        assert "Reset Password" in html
```

**Step 2: Run test to verify it fails**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestEmailService -v
```

Expected: FAIL - `ModuleNotFoundError: No module named 'services.email_service'`

**Step 3: Install SendGrid dependency**

```bash
cd backend
pip install sendgrid>=6.10.0
```

Add to `backend/requirements.txt`:

```
sendgrid>=6.10.0
```

**Step 4: Update config.py**

Add to `backend/config.py`:

```python
import os

# JWT Configuration
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "dev-secret-key-change-in-production-abc123xyz789"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 14

# Email Configuration (SendGrid)
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@trekkr.app")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
```

**Step 5: Create EmailService**

Create file `backend/services/email_service.py`:

```python
"""Email service for sending transactional emails via SendGrid."""

import os

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


class EmailService:
    """Handles sending emails via SendGrid."""

    def __init__(self):
        self.api_key = os.getenv("SENDGRID_API_KEY")
        self.from_email = os.getenv("SENDGRID_FROM_EMAIL", "noreply@trekkr.app")
        self.app_name = "Trekkr"
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

    def send_password_reset(
        self,
        to_email: str,
        username: str,
        token: str
    ) -> bool:
        """
        Send password reset email.

        Returns True on success, False on failure.
        """
        reset_url = f"{self.frontend_url}/reset-password?token={token}"

        message = Mail(
            from_email=self.from_email,
            to_emails=to_email,
            subject=f"{self.app_name} - Reset Your Password",
            html_content=self._build_reset_email_html(username, reset_url)
        )

        try:
            sg = SendGridAPIClient(self.api_key)
            sg.send(message)
            return True
        except Exception as e:
            # Log error but don't expose to user
            print(f"Email send failed: {e}")
            return False

    def _build_reset_email_html(self, username: str, reset_url: str) -> str:
        """Build HTML content for password reset email."""
        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Reset Your Password</h2>
            <p>Hi {username},</p>
            <p>We received a request to reset your password for your {self.app_name} account.</p>
            <p>Click the button below to reset your password. This link expires in 1 hour.</p>
            <p style="margin: 30px 0;">
                <a href="{reset_url}"
                   style="background-color: #4CAF50; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 4px;">
                    Reset Password
                </a>
            </p>
            <p>If you didn't request this, you can safely ignore this email.</p>
            <p>— The {self.app_name} Team</p>
        </div>
        """
```

**Step 6: Run test to verify it passes**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestEmailService -v
```

Expected: PASS (3 tests)

**Step 7: Commit**

```bash
git add backend/services/email_service.py backend/config.py backend/requirements.txt backend/tests/test_password_management.py
git commit -m "feat: add EmailService for SendGrid password reset emails"
```

---

## Task 8: Add Forgot Password to PasswordService

**Files:**
- Modify: `backend/services/password_service.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_password_management.py`:

```python
@pytest.mark.integration
class TestPasswordServiceForgotPassword:
    """Test PasswordService.request_password_reset method."""

    @patch('services.password_service.EmailService')
    def test_request_reset_creates_token(
        self,
        mock_email_class,
        db_session: Session
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
        token = db_session.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id
        ).first()

        assert token is not None
        assert token.used_at is None
        assert token.expires_at > datetime.utcnow()

        # Verify email was sent
        mock_email_instance.send_password_reset.assert_called_once()
        call_args = mock_email_instance.send_password_reset.call_args
        assert call_args[1]["to_email"] == "forgot@example.com"
        assert call_args[1]["username"] == "forgot_user"

    @patch('services.password_service.EmailService')
    def test_request_reset_nonexistent_email_silent(
        self,
        mock_email_class,
        db_session: Session
    ):
        """Verify no error for non-existent email (prevents enumeration)."""
        mock_email_instance = MagicMock()
        mock_email_class.return_value = mock_email_instance

        service = PasswordService(db_session)

        # Should not raise
        service.request_password_reset("nobody@example.com")

        # Verify no email was sent
        mock_email_instance.send_password_reset.assert_not_called()

    @patch('services.password_service.EmailService')
    def test_request_reset_invalidates_old_tokens(
        self,
        mock_email_class,
        db_session: Session
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
        tokens = db_session.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None)
        ).all()

        assert len(tokens) == 1
```

**Step 2: Run test to verify it fails**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestPasswordServiceForgotPassword -v
```

Expected: FAIL - `AttributeError: 'PasswordService' object has no attribute 'request_password_reset'`

**Step 3: Add request_password_reset to PasswordService**

Update `backend/services/password_service.py`:

```python
"""Password management service for change/forgot/reset flows."""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from models.password_reset import PasswordResetToken
from models.user import User
from services.auth import hash_password, verify_password
from services.email_service import EmailService

RESET_TOKEN_EXPIRY_HOURS = 1


class PasswordService:
    """Handles password change, forgot, and reset operations."""

    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService()

    def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str
    ) -> bool:
        """
        Change password for authenticated user.

        Returns True on success, False if current password is wrong.
        Increments token_version to invalidate all existing sessions.
        """
        if not verify_password(current_password, user.hashed_password):
            return False

        user.hashed_password = hash_password(new_password)
        user.token_version += 1

        self.db.commit()
        return True

    def request_password_reset(self, email: str) -> None:
        """
        Request password reset for email.

        Sends reset email if user exists, fails silently otherwise
        to prevent email enumeration.
        """
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            return  # Silent fail

        # Generate secure random token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        # Invalidate any existing unused tokens for this user
        self.db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None)
        ).delete()

        # Create new token
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(hours=RESET_TOKEN_EXPIRY_HOURS)
        )
        self.db.add(reset_token)
        self.db.commit()

        # Send email with raw token
        self.email_service.send_password_reset(
            to_email=user.email,
            username=user.username,
            token=raw_token
        )
```

**Step 4: Run test to verify it passes**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestPasswordServiceForgotPassword -v
```

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/services/password_service.py backend/tests/test_password_management.py
git commit -m "feat: add request_password_reset to PasswordService"
```

---

## Task 9: Add Reset Password to PasswordService

**Files:**
- Modify: `backend/services/password_service.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_password_management.py`:

```python
import hashlib


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
            new_password="NewPassword789"
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
            new_password="NewPassword789"
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
            new_password="NewPassword789"
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
            new_password="NewPassword789"
        )

        assert result is False
```

**Step 2: Run test to verify it fails**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestPasswordServiceResetPassword -v
```

Expected: FAIL - `AttributeError: 'PasswordService' object has no attribute 'reset_password'`

**Step 3: Add reset_password to PasswordService**

Add to `backend/services/password_service.py`:

```python
    def reset_password(self, raw_token: str, new_password: str) -> bool:
        """
        Reset password using token from email.

        Returns True on success, False if token invalid/expired/used.
        Increments token_version to invalidate all existing sessions.
        """
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        reset_token = self.db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > datetime.utcnow()
        ).first()

        if not reset_token:
            return False

        # Update password
        user = reset_token.user
        user.hashed_password = hash_password(new_password)
        user.token_version += 1

        # Mark token as used
        reset_token.used_at = datetime.utcnow()

        self.db.commit()
        return True
```

**Step 4: Run test to verify it passes**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestPasswordServiceResetPassword -v
```

Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/services/password_service.py backend/tests/test_password_management.py
git commit -m "feat: add reset_password to PasswordService"
```

---

## Task 10: Add Change Password Endpoint

**Files:**
- Modify: `backend/routers/auth.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_password_management.py`:

```python
from fastapi.testclient import TestClient


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
                "new_password": "NewPassword456"
            },
            headers={"Authorization": f"Bearer {token}"}
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
                "new_password": "NewPassword456"
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 401

    def test_change_password_unauthenticated(self, client: TestClient):
        """Verify endpoint requires authentication."""
        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "OldPass123",
                "new_password": "NewPass456"
            }
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
                "new_password": "weak"
            },
            headers={"Authorization": f"Bearer {token}"}
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
                "new_password": "NewPassword456"
            },
            headers={"Authorization": f"Bearer {old_token}"}
        )
        assert response.status_code == 200

        # Try to use old token
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {old_token}"}
        )

        assert response.status_code == 401
```

**Step 2: Run test to verify it fails**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestChangePasswordEndpoint -v
```

Expected: FAIL - 404 Not Found (endpoint doesn't exist)

**Step 3: Add endpoint to auth router**

Add to `backend/routers/auth.py`:

First, add imports at the top:
```python
from schemas.auth import (
    ChangePasswordRequest,
    DeviceResponse,
    DeviceUpdateRequest,
    MessageResponse,
    TokenRefresh,
    TokenResponse,
    UserRegister,
    UserResponse,
)
from services.password_service import PasswordService
```

Then add the endpoint:
```python
@router.post("/change-password", response_model=MessageResponse)
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change password for the authenticated user.

    Requires: Authorization header with Bearer token
    Body: current_password, new_password
    Returns: success message
    Raises: 401 if current password is wrong, 422 if new password invalid

    Note: All existing sessions will be invalidated after password change.
    """
    password_service = PasswordService(db)
    success = password_service.change_password(
        user=current_user,
        current_password=request.current_password,
        new_password=request.new_password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )

    return {"message": "Password changed successfully. Please log in again."}
```

**Step 4: Run test to verify it passes**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestChangePasswordEndpoint -v
```

Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add backend/routers/auth.py backend/tests/test_password_management.py
git commit -m "feat: add POST /api/auth/change-password endpoint"
```

---

## Task 11: Add Forgot Password Endpoint

**Files:**
- Modify: `backend/routers/auth.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_password_management.py`:

```python
@pytest.mark.integration
class TestForgotPasswordEndpoint:
    """Test POST /api/auth/forgot-password endpoint."""

    @patch('services.password_service.EmailService')
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
            json={"email": "forgotendpoint@example.com"}
        )

        assert response.status_code == 200
        assert "password reset link" in response.json()["message"].lower()

    @patch('services.password_service.EmailService')
    def test_forgot_password_nonexistent_email_same_response(
        self,
        mock_email_class,
        client: TestClient,
    ):
        """Verify same response for non-existent email (no enumeration)."""
        response = client.post(
            "/api/auth/forgot-password",
            json={"email": "nonexistent@example.com"}
        )

        # Should return 200 with same message
        assert response.status_code == 200
        assert "password reset link" in response.json()["message"].lower()

    def test_forgot_password_invalid_email_format(self, client: TestClient):
        """Verify invalid email format is rejected."""
        response = client.post(
            "/api/auth/forgot-password",
            json={"email": "not-an-email"}
        )

        assert response.status_code == 422
```

**Step 2: Run test to verify it fails**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestForgotPasswordEndpoint -v
```

Expected: FAIL - 404 Not Found

**Step 3: Add endpoint to auth router**

Add import at top of `backend/routers/auth.py`:
```python
from schemas.auth import (
    ChangePasswordRequest,
    DeviceResponse,
    DeviceUpdateRequest,
    ForgotPasswordRequest,
    MessageResponse,
    TokenRefresh,
    TokenResponse,
    UserRegister,
    UserResponse,
)
```

Add endpoint:
```python
@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Request a password reset email.

    Body: email
    Returns: success message (always, to prevent email enumeration)

    If the email exists, a password reset link will be sent.
    """
    password_service = PasswordService(db)
    password_service.request_password_reset(request.email)

    return {"message": "If an account with that email exists, a password reset link has been sent."}
```

**Step 4: Run test to verify it passes**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestForgotPasswordEndpoint -v
```

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/routers/auth.py backend/tests/test_password_management.py
git commit -m "feat: add POST /api/auth/forgot-password endpoint"
```

---

## Task 12: Add Reset Password Endpoint

**Files:**
- Modify: `backend/routers/auth.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_password_management.py`:

```python
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
                "new_password": "NewPassword789"
            }
        )

        assert response.status_code == 200
        assert "successfully" in response.json()["message"].lower()

    def test_reset_password_invalid_token(self, client: TestClient):
        """Verify reset fails with invalid token."""
        response = client.post(
            "/api/auth/reset-password",
            json={
                "token": "totally_invalid_token",
                "new_password": "NewPassword789"
            }
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
                "new_password": "NewPassword789"
            }
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
                "new_password": "NewPassword789"
            }
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
                "new_password": "weak"
            }
        )

        assert response.status_code == 422
```

**Step 2: Run test to verify it fails**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestResetPasswordEndpoint -v
```

Expected: FAIL - 404 Not Found

**Step 3: Add endpoint to auth router**

Add import at top of `backend/routers/auth.py`:
```python
from schemas.auth import (
    ChangePasswordRequest,
    DeviceResponse,
    DeviceUpdateRequest,
    ForgotPasswordRequest,
    MessageResponse,
    ResetPasswordRequest,
    TokenRefresh,
    TokenResponse,
    UserRegister,
    UserResponse,
)
```

Add endpoint:
```python
@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Reset password using a token from email.

    Body: token, new_password
    Returns: success message
    Raises: 400 if token invalid/expired/used, 422 if new password invalid
    """
    password_service = PasswordService(db)
    success = password_service.reset_password(
        raw_token=request.token,
        new_password=request.new_password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or already used reset token"
        )

    return {"message": "Password reset successfully. Please log in with your new password."}
```

**Step 4: Run test to verify it passes**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py::TestResetPasswordEndpoint -v
```

Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add backend/routers/auth.py backend/tests/test_password_management.py
git commit -m "feat: add POST /api/auth/reset-password endpoint"
```

---

## Task 13: Run All Tests and Final Verification

**Step 1: Run all password management tests**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_password_management.py -v
```

Expected: All tests pass (approximately 30+ tests)

**Step 2: Run all auth tests to ensure no regression**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_auth_router.py -v
```

Expected: All existing tests pass

**Step 3: Run full test suite**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest -v
```

Expected: All tests pass

**Step 4: Final commit with summary**

```bash
git add -A
git commit -m "feat: complete password management implementation

Implements:
- POST /api/auth/change-password (authenticated)
- POST /api/auth/forgot-password (request reset email)
- POST /api/auth/reset-password (complete reset with token)

Features:
- Token versioning for session invalidation on password change/reset
- SendGrid integration for password reset emails
- SHA-256 hashed reset tokens with 1-hour expiration
- Same password validation rules as registration

All tests passing."
```

---

## Summary

This plan implements password management in 13 tasks following TDD:

| Task | Component | Tests |
|------|-----------|-------|
| 1 | Database migration | - |
| 2 | User.token_version | 2 |
| 3 | PasswordResetToken model | 3 |
| 4 | Password schemas | 7 |
| 5 | Token version in auth service | 2 |
| 6 | PasswordService.change_password | 2 |
| 7 | EmailService | 3 |
| 8 | PasswordService.request_password_reset | 3 |
| 9 | PasswordService.reset_password | 4 |
| 10 | POST /change-password endpoint | 5 |
| 11 | POST /forgot-password endpoint | 3 |
| 12 | POST /reset-password endpoint | 5 |
| 13 | Final verification | - |

**Total: ~39 new tests**
