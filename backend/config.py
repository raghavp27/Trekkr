import os

# JWT Configuration
# In production, set SECRET_KEY environment variable to a secure random value
ENV = os.getenv("ENV", "development").lower()

_DEFAULT_SECRET_KEY = "dev-secret-key-change-in-production-abc123xyz789"
SECRET_KEY = os.getenv("SECRET_KEY", _DEFAULT_SECRET_KEY)  # Default for development only
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 14

# Email Configuration (SendGrid)
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@trekkr.app")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


def validate_config() -> None:
    """
    Validate required configuration.

    This is intentionally strict only in production so that local development
    and tests can run with minimal environment setup.
    """
    if ENV != "production":
        return

    errors: list[str] = []

    if not SECRET_KEY or SECRET_KEY == _DEFAULT_SECRET_KEY:
        errors.append("SECRET_KEY must be set to a secure value in production")
    elif len(SECRET_KEY) < 32:
        errors.append("SECRET_KEY must be at least 32 characters in production")

    if not SENDGRID_API_KEY:
        errors.append("SENDGRID_API_KEY must be set in production")

    if not SENDGRID_FROM_EMAIL:
        errors.append("SENDGRID_FROM_EMAIL must be set in production")

    if not FRONTEND_URL or not FRONTEND_URL.startswith(("http://", "https://")):
        errors.append("FRONTEND_URL must be an http(s) URL in production")
    elif FRONTEND_URL.startswith("http://") and not FRONTEND_URL.startswith("http://localhost"):
        errors.append("FRONTEND_URL should use HTTPS in production (http:// only allowed for localhost)")

    if errors:
        raise RuntimeError("Invalid configuration:\n- " + "\n- ".join(errors))

