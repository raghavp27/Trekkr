from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db
from models.device import Device
from models.user import User
from routers.location import limiter
from schemas.auth import (
    AccountDeleteRequest,
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
from services.auth import (
    create_tokens,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from services.password_service import PasswordService

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user account and return authentication tokens.

    Body: email, username, password
    Returns: access_token, refresh_token, token_type
    Raises: 400 if email/username exists, 422 if validation fails
    """
    # Check if email already exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Check if username already exists
    existing_username = db.query(User).filter(User.username == user_data.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    # Create new user
    hashed_password = hash_password(user_data.password)
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Return tokens
    return create_tokens(new_user)


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Authenticate an existing user and return authentication tokens.

    Form data: username (email or username), password
    Returns: access_token, refresh_token, token_type
    Raises: 401 if invalid credentials
    """
    # Find user by email OR username (OAuth2 form uses 'username' field for both)
    user = db.query(User).filter(
        (User.email == form_data.username) | (User.username == form_data.username)
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email/username or password",
        )

    # Verify password
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email/username or password",
        )

    # Return tokens (OAuth2 expects 'access_token' and 'token_type')
    tokens = create_tokens(user)
    return tokens


@router.post("/logout", response_model=MessageResponse)
def logout(current_user: User = Depends(get_current_user)):
    """
    Logout the current authenticated user.

    Requires: Authorization header with Bearer token
    Returns: success message
    Note: Client must clear tokens from storage (stateless JWT)
    """
    return {"message": "Successfully logged out"}


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(token_data: TokenRefresh, db: Session = Depends(get_db)):
    """
    Obtain new authentication tokens using a valid refresh token.

    Body: refresh_token
    Returns: new access_token, refresh_token, token_type
    Raises: 401 if token invalid/expired or user not found
    """
    payload = decode_token(token_data.refresh_token)

    # Ensure it's a refresh token
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Find user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Validate token version (session invalidation check)
    token_version = payload.get("token_ver")
    if token_version is None or token_version != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalidated. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Return new tokens
    return create_tokens(user)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Retrieve the currently authenticated user's profile information.

    Requires: Authorization header with Bearer token
    Returns: user id, email, username, created_at
    Raises: 401 if not authenticated or token invalid
    """
    return current_user


@router.post("/change-password", response_model=MessageResponse)
@limiter.limit("10/minute")
def change_password(
    request: Request,
    payload: ChangePasswordRequest,
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

    Rate limit: 10 requests per minute per user.
    """
    # Store user_id in request state for rate limiting
    request.state.user_id = current_user.id

    password_service = PasswordService(db)
    success = password_service.change_password(
        user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    return {"message": "Password changed successfully. Please log in again."}


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit("5/minute")
def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Request a password reset email.

    Body: email
    Returns: success message (always, to prevent email enumeration)

    If the email exists, a password reset link will be sent.

    Rate limit: 5 requests per minute per IP/user.
    """
    password_service = PasswordService(db)
    password_service.request_password_reset(payload.email)

    return {
        "message": (
            "If an account with that email exists, a password reset link has been sent."
        )
    }


@router.post("/reset-password", response_model=MessageResponse)
@limiter.limit("5/minute")
def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Reset password using a token from email.

    Body: token, new_password
    Returns: success message
    Raises: 400 if token invalid/expired/used, 422 if new password invalid

    Rate limit: 5 requests per minute per IP/user.
    """
    password_service = PasswordService(db)
    success = password_service.reset_password(
        raw_token=payload.token,
        new_password=payload.new_password,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or already used reset token",
        )

    return {
        "message": "Password reset successfully. Please log in with your new password."
    }


@router.patch("/device", response_model=DeviceResponse)
def update_device(
    device_data: DeviceUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update the current user's device metadata.

    Auto-creates device if user doesn't have one yet (single device per user).
    Requires: Authorization header with Bearer token
    Body: device_name, platform, app_version (all optional)
    Returns: updated device information
    """
    # Get or create user's device
    device = db.query(Device).filter(Device.user_id == current_user.id).first()

    if not device:
        # Create first device with provided metadata
        device = Device(
            user_id=current_user.id,
            device_name=device_data.device_name or "My Phone",
            platform=device_data.platform or "unknown",
            app_version=device_data.app_version,
        )
        db.add(device)
    else:
        # Update existing device metadata
        if device_data.device_name is not None:
            device.device_name = device_data.device_name
        if device_data.platform is not None:
            device.platform = device_data.platform
        if device_data.app_version is not None:
            device.app_version = device_data.app_version

    db.commit()
    db.refresh(device)

    return device


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    request: AccountDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Permanently delete the authenticated user's account and all associated data.

    This action is irreversible. Deletes:
    - User account and credentials
    - Device record
    - All location visit history
    - All achievement unlocks
    - All ingestion batch records

    Global H3 cell registry is preserved (shared across users).

    Example request:
    ```json
    {
      "password": "MySecurePass123",
      "confirmation": "DELETE"
    }
    ```

    The confirmation field must contain exactly "DELETE" (case-sensitive).

    Requires: Authorization header with Bearer token
    Body: password (current password), confirmation (must be "DELETE")
    Returns: 204 No Content on success
    Raises:
      - 401 Unauthorized if password is incorrect
      - 422 Validation Error if confirmation is invalid
    """
    # Verify current password
    if not verify_password(request.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )

    # Delete user (CASCADE constraints handle related data automatically)
    db.delete(current_user)
    db.commit()

    # Return 204 No Content (no response body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

