"""Password reset token model for account recovery."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import backref, relationship

from database import Base


class PasswordResetToken(Base):
    """Stores hashed password reset tokens with expiration."""

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Let the database enforce ON DELETE CASCADE without SQLAlchemy issuing
    # "set user_id = NULL" updates on delete.
    user = relationship(
        "User",
        backref=backref("password_reset_tokens", passive_deletes=True),
    )

