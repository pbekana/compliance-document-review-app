from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.security import create_access_token, hash_password, verify_password
from app.db.database import get_db
from app.model.user import User, UserRole
from app.schema.auth import AuthResponse, UserLogin
from app.schema.user import UserRegister, UserResponse


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"]
)


def serialize_user(user: User) -> dict:
    role_value = getattr(user.role, "value", user.role)
    if isinstance(role_value, str):
        if role_value.lower() == "advisor":
            role = "ADVISOR"
        elif role_value.lower() in {"compliance_officer", "officer"}:
            role = "COMPLIANCE_OFFICER"
        else:
            role = role_value.upper()
    else:
        role = str(role_value).upper()

    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": role,
    }


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED
)
def signup_user(
    user_data: UserRegister,
    db: Session = Depends(get_db),
):
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered",
        )

    role_value = user_data.role.strip().lower()
    if role_value == "officer":
        role_value = "compliance_officer"
    if role_value == "compliance_officer":
        role = UserRole.COMPLIANCE_OFFICER
    else:
        role = UserRole.ADVISOR

    new_user = User(
        full_name=user_data.full_name,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        role=role,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    access_token = create_access_token({
        "sub": str(new_user.id),
        "role": new_user.role.value,
    })

    return {
        "user": serialize_user(new_user),
        "token": access_token,
    }


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def register_user_alias(
    user_data: UserRegister,
    db: Session = Depends(get_db),
):
    return signup_user(user_data=user_data, db=db)


@router.post(
    "/login",
    response_model=AuthResponse,
)
def login_user(
    user_data: UserLogin,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == user_data.email).first()

    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
    })

    return {
        "user": serialize_user(user),
        "token": access_token,
    }


@router.post("/logout")
def logout_user(
    current_user: User = Depends(get_current_user),
):
    return {
        "message": "Logged out successfully. JWTs are stateless; remove the token from the client storage.",
        "user": serialize_user(current_user),
    }


@router.get(
    "/me",
    response_model=dict,
)
def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    return {"user": serialize_user(current_user)}


