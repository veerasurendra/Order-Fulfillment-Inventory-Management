from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.models.user import User, RefreshToken
from app.models.warehouse import WarehouseUser
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session):
        super().__init__(User, db)

    def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email.lower().strip())
        return self.db.scalar(stmt)

    def get_by_username(self, username: str) -> Optional[User]:
        stmt = select(User).where(User.username == username.strip())
        return self.db.scalar(stmt)

    def get_by_username_or_email(self, identifier: str) -> Optional[User]:
        ident = identifier.strip()
        stmt = select(User).where((User.username == ident) | (User.email == ident.lower()))
        return self.db.scalar(stmt)

    def get_user_warehouse_ids(self, user_id: int) -> List[int]:
        stmt = select(WarehouseUser.warehouse_id).where(WarehouseUser.user_id == user_id)
        return list(self.db.scalars(stmt).all())

    # Refresh Token Management
    def save_refresh_token(
        self,
        user_id: int,
        token_jti: str,
        family_id: str,
        expires_at: datetime,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            token_jti=token_jti,
            family_id=family_id,
            expires_at=expires_at,
            is_revoked=False,
        )
        self.db.add(token)
        self.db.flush()
        return token

    def get_refresh_token_by_jti(self, token_jti: str) -> Optional[RefreshToken]:
        stmt = select(RefreshToken).where(RefreshToken.token_jti == token_jti)
        return self.db.scalar(stmt)

    def revoke_refresh_token(self, token_jti: str) -> None:
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.token_jti == token_jti)
            .values(is_revoked=True)
        )
        self.db.execute(stmt)
        self.db.flush()

    def revoke_refresh_token_family(self, family_id: str) -> None:
        """Revoke all tokens in a family if reuse is detected."""
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id)
            .values(is_revoked=True)
        )
        self.db.execute(stmt)
        self.db.flush()

    def revoke_all_user_tokens(self, user_id: int) -> None:
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .values(is_revoked=True)
        )
        self.db.execute(stmt)
        self.db.flush()
