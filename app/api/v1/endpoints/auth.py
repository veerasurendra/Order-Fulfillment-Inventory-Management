from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.dependencies.auth import get_current_user
from app.models.user import User
from app.services.auth_service import AuthService
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    PasswordChangeRequest,
    UserResponse,
)
from app.schemas.common import SuccessResponse, MessageResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=SuccessResponse[UserResponse], status_code=status.HTTP_201_CREATED)
def register(
    req: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Register a new customer account or user."""
    auth_service = AuthService(db)
    client_ip = request.client.host if request.client else None
    user = auth_service.register(req, ip_address=client_ip)
    return SuccessResponse(data=user, message="User registered successfully")


@router.post("/login", response_model=SuccessResponse[TokenResponse])
def login(
    req: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Authenticate and obtain JWT access and refresh tokens."""
    auth_service = AuthService(db)
    client_ip = request.client.host if request.client else None
    tokens = auth_service.login(req, ip_address=client_ip)
    return SuccessResponse(data=tokens, message="Login successful")


@router.post("/refresh", response_model=SuccessResponse[TokenResponse])
def refresh_tokens(
    req: RefreshRequest,
    db: Session = Depends(get_db),
):
    """Rotate and refresh access & refresh tokens."""
    auth_service = AuthService(db)
    tokens = auth_service.refresh_tokens(req.refresh_token)
    return SuccessResponse(data=tokens, message="Tokens refreshed successfully")


@router.post("/logout", response_model=MessageResponse)
def logout(
    req: RefreshRequest,
    db: Session = Depends(get_db),
):
    """Revoke refresh token and terminate active session."""
    auth_service = AuthService(db)
    auth_service.logout(req.refresh_token)
    return MessageResponse(message="Successfully logged out")


@router.get("/me", response_model=SuccessResponse[UserResponse])
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve current authenticated user profile and warehouse authorizations."""
    auth_service = AuthService(db)
    me = auth_service.get_me(current_user.id)
    return SuccessResponse(data=me)


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    req: PasswordChangeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change current user password and invalidate active refresh tokens."""
    auth_service = AuthService(db)
    client_ip = request.client.host if request.client else None
    auth_service.change_password(current_user.id, req, ip_address=client_ip)
    return MessageResponse(message="Password changed successfully. Please log in again with your new credentials.")
