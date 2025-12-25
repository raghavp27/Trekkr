from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from schemas.auth import (
    MessageResponse,
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

