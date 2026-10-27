"""Authentication endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from src.api.schemas import Token, UserCreate, UserResponse
from src.auth.dependencies import get_current_user
from src.auth.security import (
    create_access_token,
    get_password_hash,
    get_valid_department_names,
    is_allowed_staff_email,
    is_valid_department_name,
    normalize_department_name,
    resolve_staff_department,
    verify_password,
)
from src.db.connection import get_db
from src.db.crud import create_user, get_user_by_username
from src.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/departments")
def list_departments() -> dict:
    return {"departments": get_valid_department_names()}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    role = payload.role.strip().lower()
    email = payload.email.strip().lower()
    department = normalize_department_name(payload.department)

    if role == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator accounts cannot be created through public registration.",
        )

    if role not in {"student", "faculty", "staff"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported role.",
        )

    if role in {"staff", "faculty"}:
        if not is_allowed_staff_email(email):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Staff and faculty accounts require an institutional email from the configured allowed domains.",
            )
        if department is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="A valid department is required for staff and faculty registration.",
            )
        resolved_department = resolve_staff_department(email, department)
        if resolved_department is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="A valid department is required for staff and faculty registration.",
            )
        department = resolved_department

    if role == "student" and department is not None:
        department = None

    if get_user_by_username(db, payload.username):
        raise HTTPException(status_code=409, detail="Username is already registered.")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email is already registered.")
    return create_user(
        db,
        username=payload.username.strip(),
        email=email,
        hashed_password=get_password_hash(payload.password),
        role=role,
        department=department,
    )


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> dict:
    user = get_user_by_username(db, form_data.username)
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "access_token": create_access_token({"sub": user.username}),
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
    }


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user