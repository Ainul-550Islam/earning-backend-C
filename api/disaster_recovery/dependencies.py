"""
FastAPI Dependencies for Disaster Recovery System
"""
from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from jose import JWTError, jwt
from pydantic import BaseModel

from .config import settings

# ── Database ──────────────────────────────────────────────────────────────────
engine = create_engine(
    settings.database.url,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Auth ──────────────────────────────────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

ALGORITHM = "HS256"


class CurrentUser(BaseModel):
    id: str
    email: str
    role: str = "operator"

    def is_admin(self) -> bool:
        return self.role in ("admin", "superadmin")

    def is_operator(self) -> bool:
        return self.role in ("admin", "superadmin", "operator")


def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return CurrentUser(
            id=user_id,
            email=payload.get("email", ""),
            role=payload.get("role", "operator")
        )
    except JWTError:
        raise credentials_exception


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


def require_operator(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_operator():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator access required"
        )
    return user
