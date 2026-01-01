"""Email service for sending transactional emails via SendGrid."""

import logging
from html import escape

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from config import FRONTEND_URL, SENDGRID_API_KEY, SENDGRID_FROM_EMAIL


logger = logging.getLogger(__name__)


class EmailService:
    """Handles sending emails via SendGrid."""

    def __init__(self):
        # Config values are read at import-time; restart the server after changing env.
        raw_key = (SENDGRID_API_KEY or "").strip()
        # Common misconfig: pasting "Bearer <key>" into env var.
        if raw_key.lower().startswith("bearer "):
            raw_key = raw_key.split(" ", 1)[1].strip()
        self.api_key = raw_key
        self.from_email = SENDGRID_FROM_EMAIL
        self.app_name = "Trekkr"
        self.frontend_url = FRONTEND_URL

    def send_password_reset(self, to_email: str, username: str, token: str) -> bool:
        """
        Send password reset email.

        Returns True on success, False on failure.
        """
        reset_url = f"{self.frontend_url}/reset-password?token={token}"

        message = Mail(
            from_email=self.from_email,
            to_emails=to_email,
            subject=f"{self.app_name} - Reset Your Password",
            html_content=self._build_reset_email_html(username=username, reset_url=reset_url),
        )

        # Minimal diagnostics (no secrets/PII): helps catch env/key issues.
        logger.info(
            "send_password_reset: sendgrid_config",
            extra={
                "sendgrid_api_key_present": bool(self.api_key),
                "sendgrid_api_key_len": len(self.api_key),
                "sendgrid_api_key_starts_sg": self.api_key.startswith("SG."),
                "sendgrid_from_email_set": bool(self.from_email),
                "frontend_url_set": bool(self.frontend_url),
            },
        )

        try:
            sg = SendGridAPIClient(self.api_key)
            sg.send(message)
            return True
        except Exception as e:
            # Avoid leaking provider errors to end users; log for operators.
            logger.exception("Email send failed: %s", e)
            return False

    def _build_reset_email_html(self, *, username: str, reset_url: str) -> str:
        """Build HTML content for password reset email.
        
        Note: Escapes user input to prevent XSS attacks in email clients.
        """
        # Escape user input to prevent XSS
        safe_username = escape(username)
        safe_reset_url = escape(reset_url)
        
        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Reset Your Password</h2>
            <p>Hi {safe_username},</p>
            <p>We received a request to reset your password for your {self.app_name} account.</p>
            <p>Click the button below to reset your password. This link expires in 1 hour.</p>
            <p style="margin: 30px 0;">
                <a href="{safe_reset_url}"
                   style="background-color: #4CAF50; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 4px;">
                    Reset Password
                </a>
            </p>
            <p>If you didn't request this, you can safely ignore this email.</p>
            <p>— The {self.app_name} Team</p>
        </div>
        """

