"""JWT authentication endpoints and dependencies for the FastAPI service."""

from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg2 import IntegrityError
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field

from .database import get_db

load_dotenv()
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

router = APIRouter(tags=["authentication"])
bearer_scheme = HTTPBearer()

JWT_ALGORITHM = "HS256"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


class Credentials(BaseModel):
    """The JSON body accepted by both registration and login."""

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUser(BaseModel):
    id: int
    username: str
    role: str


def _jwt_secret() -> str:
    if not JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY must be configured in the environment or .env file.")
    return JWT_SECRET_KEY


def create_access_token(user: CurrentUser) -> str:
    """Create a short-lived token containing only non-sensitive user claims."""
    expires_at = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "exp": expires_at,
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_access_token(token: str) -> CurrentUser:
    """Decode a signed token for HTTP or WebSocket authorization checks."""
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
        return CurrentUser(
            id=int(payload["sub"]),
            username=str(payload["username"]),
            role=str(payload["role"]),
        )
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise _invalid_credentials() from None


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(credentials: Credentials, db=Depends(get_db)) -> TokenResponse:
    """Create an ev_driver account and immediately return a JWT session token."""
    password_bytes = credentials.password.encode("utf-8")
    password_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")
    try:
        with db.cursor(cursor_factory=RealDictCursor) as cursor:
            # Role is intentionally omitted: all self-registered accounts use the
            # table's safe default instead of accepting client-controlled privileges.
            cursor.execute(
                """
                INSERT INTO users (username, hashed_password)
                VALUES (%s, %s)
                RETURNING id, username, role;
                """,
                (credentials.username, password_hash),
            )
            row = cursor.fetchone()
        db.commit()
    except (IntegrityError, sqlite3.IntegrityError):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username is already registered.",
        ) from None

    user = CurrentUser(**row)
    return TokenResponse(access_token=create_access_token(user))


@router.post("/login", response_model=TokenResponse)
def login(credentials: Credentials, db=Depends(get_db)) -> TokenResponse:
    """Verify a password against its bcrypt hash and issue a JWT."""
    with db.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            """
            SELECT id, username, hashed_password, role
            FROM users
            WHERE username = %s;
            """,
            (credentials.username,),
        )
        row = cursor.fetchone()

    if not row:
        raise _invalid_credentials()

    stored_hash = row["hashed_password"]
    if isinstance(stored_hash, str):
        stored_hash = stored_hash.encode("utf-8")

    if not bcrypt.checkpw(credentials.password.encode("utf-8"), stored_hash):
        raise _invalid_credentials()

    user = CurrentUser(id=row["id"], username=row["username"], role=row["role"])
    return TokenResponse(access_token=create_access_token(user))


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db=Depends(get_db),
) -> CurrentUser:
    """Validate the JWT and confirm that its user still exists in PostgreSQL."""
    token_user = decode_access_token(credentials.credentials)

    with db.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("SELECT id, username, role FROM users WHERE id = %s;", (token_user.id,))
        row = cursor.fetchone()
    if not row:
        raise _invalid_credentials()
    return CurrentUser(**row)
