# Password Management Design

## Overview

Implement complete password management for Trekkr: change password for authenticated users, and forgot/reset password flow via email for account recovery.

**Key Decisions:**
- Token versioning for session invalidation (increment on password change)
- SendGrid for transactional email delivery
- Database-stored reset tokens (hashed) with 1-hour expiration
- Reuse existing password validation rules (8+ chars, upper, lower, number)
- TDD approach: write tests first, then implementation

---

## Database Schema

### 1. User Model Update

Add `token_version` field to existing User model for session invalidation:

```python
# backend/models/user.py - add to existing User model
token_version = Column(Integer, default=1, nullable=False)
```

### 2. New Password Reset Token Model

```python
# backend/models/password_reset.py (new file)
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA-256 hash
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)  # NULL = unused, timestamp = used
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="password_reset_tokens")
```

### 3. Migration

**File:** `backend/alembic/versions/20251230_XXXX_add_password_management.py`

```python
def upgrade():
    # Add token versioning to users
    op.add_column('users', sa.Column('token_version', sa.Integer(), nullable=False, server_default='1'))

    # Create password reset tokens table
    op.create_table('password_reset_tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(64), unique=True, nullable=False, index=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

def downgrade():
    op.drop_table('password_reset_tokens')
    op.drop_column('users', 'token_version')
```

---

## API Endpoints

### Endpoint 1: Change Password

```
POST /api/auth/change-password
Authentication: Required (Bearer token)
```

**Request:**
```json
{
  "current_password": "OldPass123",
  "new_password": "NewPass456"
}
```

**Response (200):**
```json
{
  "message": "Password changed successfully. Please log in again."
}
```

**Errors:**
- 401: Wrong current password
- 422: New password validation failed

---

### Endpoint 2: Forgot Password

```
POST /api/auth/forgot-password
Authentication: Not required
```

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response (200):** Always returns same message to prevent email enumeration:
```json
{
  "message": "If an account with that email exists, a password reset link has been sent."
}
```

---

### Endpoint 3: Reset Password

```
POST /api/auth/reset-password
Authentication: Not required
```

**Request:**
```json
{
  "token": "raw_token_from_email_link",
  "new_password": "BrandNew789"
}
```

**Response (200):**
```json
{
  "message": "Password reset successfully. Please log in with your new password."
}
```

**Errors:**
- 400: Token invalid, expired, or already used
- 422: New password validation failed

---

## Pydantic Schemas

**File:** `backend/schemas/auth.py` (add to existing)

```python
class ChangePasswordRequest(BaseModel):
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
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        # Same validation as ChangePasswordRequest
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

---

## Service Layer

### Password Service

**File:** `backend/services/password_service.py` (new)

```python
import secrets
import hashlib
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from models.user import User
from models.password_reset import PasswordResetToken
from services.auth import hash_password, verify_password
from services.email_service import EmailService

RESET_TOKEN_EXPIRY_HOURS = 1


class PasswordService:
    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService()

    def change_password(self, user: User, current_password: str, new_password: str) -> bool:
        """Change password for authenticated user. Returns True on success."""
        # 1. Verify current password
        if not verify_password(current_password, user.hashed_password):
            return False

        # 2. Hash and update password
        user.hashed_password = hash_password(new_password)

        # 3. Increment token version (invalidates all sessions)
        user.token_version += 1

        self.db.commit()
        return True

    def request_password_reset(self, email: str) -> None:
        """Request password reset. Sends email if user exists, fails silently otherwise."""
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            return  # Silent fail to prevent email enumeration

        # Generate secure random token (32 bytes = 256 bits)
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
        self.email_service.send_password_reset(user.email, user.username, raw_token)

    def reset_password(self, raw_token: str, new_password: str) -> bool:
        """Reset password using token. Returns True on success."""
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
        user.token_version += 1  # Invalidate all sessions

        # Mark token as used
        reset_token.used_at = datetime.utcnow()

        self.db.commit()
        return True
```

---

## Email Service

**File:** `backend/services/email_service.py` (new)

```python
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


class EmailService:
    def __init__(self):
        self.api_key = os.getenv("SENDGRID_API_KEY")
        self.from_email = os.getenv("SENDGRID_FROM_EMAIL", "noreply@trekkr.app")
        self.app_name = "Trekkr"
        self.frontend_url = os.getenv("FRONTEND_URL", "https://trekkr.app")

    def send_password_reset(self, to_email: str, username: str, token: str) -> bool:
        """Send password reset email. Returns True on success."""
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
            print(f"Email send failed: {e}")  # Replace with proper logging
            return False

    def _build_reset_email_html(self, username: str, reset_url: str) -> str:
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

---

## Auth Service Updates

**File:** `backend/services/auth.py` (modify existing)

Update `create_access_token` and `create_refresh_token` to include token version:

```python
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_tokens(user: User) -> dict:
    """Create both access and refresh tokens for a user."""
    # Include token_version in payload for session invalidation
    access_token = create_access_token(data={"sub": str(user.id), "token_ver": user.token_version})
    refresh_token = create_refresh_token(data={"sub": str(user.id), "token_ver": user.token_version})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


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

---

## Router Updates

**File:** `backend/routers/auth.py` (add to existing)

```python
from schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    # ... existing imports
)
from services.password_service import PasswordService


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

---

## Configuration

**File:** `backend/config.py` (add)

```python
# Email configuration
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@trekkr.app")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
```

**File:** `.env.example` (add)

```bash
# Email (SendGrid)
SENDGRID_API_KEY=your_sendgrid_api_key_here
SENDGRID_FROM_EMAIL=noreply@trekkr.app
FRONTEND_URL=http://localhost:3000
```

**File:** `backend/requirements.txt` (add)

```
sendgrid>=6.10.0
```

---

## Testing Strategy (TDD)

Follow test-driven development: write tests first, watch them fail (RED), then implement code to pass (GREEN).

### Test File: `backend/tests/test_password_management.py`

#### Change Password Tests

```python
def test_change_password_success(client, auth_headers, test_user):
    """Verify password change with valid current password."""
    response = client.post("/api/auth/change-password", json={
        "current_password": "OldPass123",
        "new_password": "NewPass456"
    }, headers=auth_headers)
    assert response.status_code == 200

    # Old token should no longer work (token_version incremented)
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 401


def test_change_password_wrong_current(client, auth_headers):
    """Verify rejection with incorrect current password."""
    response = client.post("/api/auth/change-password", json={
        "current_password": "WrongPass123",
        "new_password": "NewPass456"
    }, headers=auth_headers)
    assert response.status_code == 401


def test_change_password_weak_new_password(client, auth_headers):
    """Verify validation rejects weak new password."""
    response = client.post("/api/auth/change-password", json={
        "current_password": "OldPass123",
        "new_password": "weak"
    }, headers=auth_headers)
    assert response.status_code == 422


def test_change_password_unauthenticated(client):
    """Verify endpoint requires authentication."""
    response = client.post("/api/auth/change-password", json={
        "current_password": "OldPass123",
        "new_password": "NewPass456"
    })
    assert response.status_code == 401
```

#### Forgot Password Tests

```python
def test_forgot_password_existing_email(client, test_user, mock_email_service):
    """Verify reset email sent for existing user."""
    response = client.post("/api/auth/forgot-password", json={
        "email": test_user.email
    })
    assert response.status_code == 200
    mock_email_service.send_password_reset.assert_called_once()


def test_forgot_password_nonexistent_email(client, mock_email_service):
    """Verify same response for non-existent email (no enumeration)."""
    response = client.post("/api/auth/forgot-password", json={
        "email": "nobody@example.com"
    })
    assert response.status_code == 200  # Same response!
    mock_email_service.send_password_reset.assert_not_called()


def test_forgot_password_invalidates_previous_tokens(client, db, test_user):
    """Verify requesting new reset invalidates old unused tokens."""
    # Request first reset
    client.post("/api/auth/forgot-password", json={"email": test_user.email})

    # Request second reset
    client.post("/api/auth/forgot-password", json={"email": test_user.email})

    # Should only have one active token
    tokens = db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == test_user.id,
        PasswordResetToken.used_at.is_(None)
    ).all()
    assert len(tokens) == 1
```

#### Reset Password Tests

```python
def test_reset_password_valid_token(client, reset_token_for_user):
    """Verify password reset with valid token."""
    response = client.post("/api/auth/reset-password", json={
        "token": reset_token_for_user,
        "new_password": "BrandNew789"
    })
    assert response.status_code == 200


def test_reset_password_expired_token(client, expired_reset_token):
    """Verify rejection of expired token."""
    response = client.post("/api/auth/reset-password", json={
        "token": expired_reset_token,
        "new_password": "BrandNew789"
    })
    assert response.status_code == 400


def test_reset_password_already_used_token(client, db, reset_token_for_user):
    """Verify rejection of already-used token."""
    # Use the token once
    client.post("/api/auth/reset-password", json={
        "token": reset_token_for_user,
        "new_password": "BrandNew789"
    })

    # Try to use again
    response = client.post("/api/auth/reset-password", json={
        "token": reset_token_for_user,
        "new_password": "AnotherPass123"
    })
    assert response.status_code == 400


def test_reset_password_invalid_token(client):
    """Verify rejection of non-existent token."""
    response = client.post("/api/auth/reset-password", json={
        "token": "totally_invalid_token",
        "new_password": "BrandNew789"
    })
    assert response.status_code == 400


def test_reset_password_invalidates_sessions(client, reset_token_for_user, auth_headers):
    """Verify token_version increments, invalidating existing sessions."""
    client.post("/api/auth/reset-password", json={
        "token": reset_token_for_user,
        "new_password": "BrandNew789"
    })

    # Old token should no longer work
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 401


def test_reset_password_weak_new_password(client, reset_token_for_user):
    """Verify validation rejects weak new password."""
    response = client.post("/api/auth/reset-password", json={
        "token": reset_token_for_user,
        "new_password": "weak"
    })
    assert response.status_code == 422
```

#### Test Fixtures

```python
@pytest.fixture
def mock_email_service(mocker):
    """Mock EmailService to avoid sending real emails."""
    return mocker.patch("services.password_service.EmailService")


@pytest.fixture
def reset_token_for_user(db, test_user):
    """Create valid reset token for test user and return raw token."""
    import secrets
    import hashlib
    from datetime import datetime, timedelta
    from models.password_reset import PasswordResetToken

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    reset_token = PasswordResetToken(
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(hours=1)
    )
    db.add(reset_token)
    db.commit()

    return raw_token


@pytest.fixture
def expired_reset_token(db, test_user):
    """Create expired reset token for test user and return raw token."""
    import secrets
    import hashlib
    from datetime import datetime, timedelta
    from models.password_reset import PasswordResetToken

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    reset_token = PasswordResetToken(
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() - timedelta(hours=1)  # Already expired
    )
    db.add(reset_token)
    db.commit()

    return raw_token
```

---

## Implementation Order (TDD)

### Task 1: Database Migration
1. Write migration for `token_version` and `password_reset_tokens` table
2. Run migration, verify schema

### Task 2: Update User Model
1. Add `token_version` field to User model
2. Add relationship to PasswordResetToken

### Task 3: Create PasswordResetToken Model
1. Create `backend/models/password_reset.py`
2. Add to model imports

### Task 4: Change Password (TDD)
1. Write tests for change password endpoint
2. Run tests (RED - should fail)
3. Add schemas to `backend/schemas/auth.py`
4. Update `create_tokens()` to include `token_ver`
5. Update `get_current_user()` to validate token version
6. Create `PasswordService.change_password()`
7. Add endpoint to `backend/routers/auth.py`
8. Run tests (GREEN - should pass)

### Task 5: Forgot Password (TDD)
1. Write tests for forgot password endpoint
2. Run tests (RED)
3. Create `backend/services/email_service.py`
4. Create `PasswordService.request_password_reset()`
5. Add endpoint to router
6. Run tests (GREEN)

### Task 6: Reset Password (TDD)
1. Write tests for reset password endpoint
2. Run tests (RED)
3. Create `PasswordService.reset_password()`
4. Add endpoint to router
5. Run tests (GREEN)

### Task 7: Integration Testing
1. Test full flow: register → forgot → reset → login with new password
2. Test session invalidation across all scenarios

---

## Security Considerations

1. **Token Storage**: Only SHA-256 hash stored in database; raw token sent to email
2. **Email Enumeration**: Forgot password always returns same response
3. **Session Invalidation**: All sessions invalidated on password change/reset via `token_version`
4. **Token Expiration**: 1-hour expiration window limits attack surface
5. **Single-Use Tokens**: Tokens marked as used immediately after successful reset
6. **Password Validation**: Consistent rules across registration and password changes
7. **Secure Token Generation**: `secrets.token_urlsafe(32)` for cryptographically secure tokens

---

## Files to Create/Modify

### New Files
- `backend/models/password_reset.py`
- `backend/services/password_service.py`
- `backend/services/email_service.py`
- `backend/tests/test_password_management.py`
- `backend/alembic/versions/20251230_XXXX_add_password_management.py`

### Modified Files
- `backend/models/user.py` - add `token_version` field
- `backend/schemas/auth.py` - add request/response schemas
- `backend/routers/auth.py` - add 3 new endpoints
- `backend/services/auth.py` - update token creation and validation
- `backend/config.py` - add email configuration
- `backend/requirements.txt` - add `sendgrid`
- `.env.example` - add email environment variables
