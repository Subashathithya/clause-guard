"""Auth endpoints: /auth/register, /auth/login, /auth/me.

JWT Bearer tokens; passwords hashed with bcrypt. Guest (anonymous) mode stays
enabled by default via ``REQUIRE_AUTH=false`` so the existing frontend keeps
working without a login screen.
"""
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.ratelimit import enforce_rate_limit
from app.core.security import create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.services import contract_service
from app.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterInput(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=255)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        if not _EMAIL_RE.match(value.strip()):
            raise ValueError("Invalid email address")
        return value.strip().lower()


class LoginInput(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=128)


@router.post("/register", status_code=201)
def register(payload: RegisterInput, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(request, "register")
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(
        id=str(uuid.uuid4()),
        email=payload.email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _auth_response(db, user)


@router.post("/login")
def login(payload: LoginInput, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(request, "login")
    user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _auth_response(db, user)


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _public_user(db, user)


def _auth_response(db: Session, user: User) -> dict:
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "user": _public_user(db, user),
    }


def _public_user(db: Session, user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "created_at": user.created_at.isoformat(),
        "quota": {
            "monthly_limit": settings.FREE_TIER_ANALYSES_PER_MONTH,
            "used": contract_service.user_usage(db, user),
            "remaining": contract_service.user_remaining(db, user),
        },
    }