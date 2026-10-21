from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.exceptions import (
    ConflictError,
    UnauthorizedError,
    UserInactiveError,
    BadRequestError,
)
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    PasswordChangeRequest,
    UserResponse,
)
from app.core.config import settings


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UserRepository(db)
        self.audit_service = AuditService(db)

    def register(self, req: RegisterRequest, ip_address: Optional[str] = None) -> UserResponse:
        # Check existing email
        if self.repo.get_by_email(req.email):
            raise ConflictError("A user with this email already exists")

        # Check existing username
        if self.repo.get_by_username(req.username):
            raise ConflictError("A user with this username already exists")

        user = User(
            email=req.email.lower().strip(),
            username=req.username.strip(),
            hashed_password=hash_password(req.password),
            full_name=req.full_name.strip(),
            role=req.role or UserRole.CUSTOMER,
            is_active=True,
        )
        self.repo.create(user)
        self.db.commit()
        self.db.refresh(user)

        self.audit_service.log(
            action="USER_REGISTERED",
            entity="USER",
            entity_id=str(user.id),
            user_id=user.id,
            ip_address=ip_address,
            metadata_json={"username": user.username, "role": user.role.value},
        )
        self.db.commit()

        return UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            warehouses=[],
        )

    def login(self, req: LoginRequest, ip_address: Optional[str] = None) -> TokenResponse:
        user = self.repo.get_by_username_or_email(req.username_or_email)
        if not user or not verify_password(req.password, user.hashed_password):
            self.audit_service.log(
                action="FAILED_LOGIN",
                entity="USER",
                entity_id=str(user.id) if user else None,
                ip_address=ip_address,
                metadata_json={"identifier": req.username_or_email},
            )
            self.db.commit()
            raise UnauthorizedError("Invalid email/username or password")

        if not user.is_active:
            raise UserInactiveError("Inactive user account cannot authenticate")

        access_token = create_access_token(
            subject=user.id,
            role=user.role.value,
            email=user.email,
        )
        refresh_token_str, jti, expires_at = create_refresh_token(subject=user.id)
        # Store refresh token record
        self.repo.save_refresh_token(
            user_id=user.id,
            token_jti=jti,
            family_id=jti,
            expires_at=expires_at,
        )

        self.audit_service.log(
            action="LOGIN_SUCCESS",
            entity="USER",
            entity_id=str(user.id),
            user_id=user.id,
            ip_address=ip_address,
        )
        self.db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    def refresh_tokens(self, refresh_token_str: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token_str)
        except Exception:
            raise UnauthorizedError("Invalid or expired refresh token")

        if payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid token type")

        user_id = int(payload.get("sub"))
        token_jti = payload.get("jti")
        family_id = payload.get("family_id")

        token_record = self.repo.get_refresh_token_by_jti(token_jti)
        if not token_record:
            raise UnauthorizedError("Refresh token not found or already invalidated")

        # If token was already revoked, someone may be reusing it -> revoke the entire family!
        if token_record.is_revoked:
            self.repo.revoke_refresh_token_family(family_id)
            self.db.commit()
            raise UnauthorizedError("Refresh token has been revoked. Security breach detected.")

        user = self.repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise UserInactiveError("User account is inactive or not found")

        # Invalidate current refresh token (rotation)
        self.repo.revoke_refresh_token(token_jti)

        # Issue new token pair preserving the family
        new_access_token = create_access_token(
            subject=user.id,
            role=user.role.value,
            email=user.email,
        )
        new_refresh_str, new_jti, expires_at = create_refresh_token(subject=user.id, family_id=family_id)
        self.repo.save_refresh_token(
            user_id=user.id,
            token_jti=new_jti,
            family_id=family_id,
            expires_at=expires_at,
        )
        self.db.commit()

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_str,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    def logout(self, refresh_token_str: str) -> None:
        try:
            payload = decode_token(refresh_token_str)
            token_jti = payload.get("jti")
            if token_jti:
                self.repo.revoke_refresh_token(token_jti)
                self.db.commit()
        except Exception:
            pass  # Silently proceed on logout

    def get_me(self, user_id: int) -> UserResponse:
        user = self.repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedError("User not found")
        warehouses = self.repo.get_user_warehouse_ids(user_id)
        return UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            warehouses=warehouses,
        )

    def change_password(self, user_id: int, req: PasswordChangeRequest, ip_address: Optional[str] = None) -> None:
        user = self.repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedError("User not found")

        if not verify_password(req.old_password, user.hashed_password):
            raise BadRequestError("Current password is incorrect")

        user.hashed_password = hash_password(req.new_password)
        # Invalidate all active refresh tokens for security
        self.repo.revoke_all_user_tokens(user_id)

        self.audit_service.log(
            action="PASSWORD_CHANGED",
            entity="USER",
            entity_id=str(user.id),
            user_id=user.id,
            ip_address=ip_address,
        )
        self.db.commit()
