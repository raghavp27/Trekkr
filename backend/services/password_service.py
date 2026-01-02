"""Password management service for change/forgot/reset flows."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

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
        *,
        user: User,
        current_password: str,
        new_password: str,
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

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        # Clean up expired tokens globally (prevents unbounded table growth)
        self.db.query(PasswordResetToken).filter(
            PasswordResetToken.expires_at < datetime.now(timezone.utc)
        ).delete(synchronize_session=False)

        # Invalidate any existing unused tokens for this user
        self.db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        ).delete(synchronize_session=False)

        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=RESET_TOKEN_EXPIRY_HOURS),
        )
        self.db.add(reset_token)
        self.db.commit()

        self.email_service.send_password_reset(
            to_email=user.email,
            username=user.username,
            token=raw_token,
        )

    def reset_password(self, *, raw_token: str, new_password: str) -> bool:
        """
        Reset password using token from email.

        Returns True on success, False if token invalid/expired/used.
        Increments token_version to invalidate all existing sessions.
        """
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        reset_token = (
            self.db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > datetime.now(timezone.utc),
            )
            .first()
        )

        if not reset_token:
            return False

        user = reset_token.user
        user.hashed_password = hash_password(new_password)
        user.token_version += 1

        reset_token.used_at = datetime.now(timezone.utc)
        self.db.commit()
        return True

