from typing import Optional, List
from fastapi import Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_token
from app.core.exceptions import UnauthorizedError, ForbiddenError, UserInactiveError
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository

security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extract and authenticate the user from JWT Bearer token."""
    if not credentials:
        raise UnauthorizedError("Authentication token is missing. Please provide a Bearer token.")

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except Exception:
        raise UnauthorizedError("Invalid or expired authentication token.")

    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid token type. Expected access token.")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedError("Token missing subject claim.")

    user_repo = UserRepository(db)
    user = user_repo.get_by_id(int(user_id_str))
    if not user:
        raise UnauthorizedError("User associated with token no longer exists.")

    if not user.is_active:
        raise UserInactiveError("Inactive user account cannot authenticate.")

    return user


def require_role(*allowed_roles: UserRole):
    """Factory creating a FastAPI dependency that checks user role."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenError(
                f"Access forbidden. Your role '{current_user.role.value}' lacks required permissions."
            )
        return current_user

    return role_checker
