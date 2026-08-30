from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session


from app.auth.security import hash_password
from app.db.database import get_db
from app.model.user import User
from app.schema.user import UserRegister, UserResponse

router = APIRouter(
prefix="/auth",
tags=["Authentication"]
)

@router.post(
"/register",
response_model=UserResponse,
status_code=status.HTTP_201_CREATED
)
def register_user(
   user_data: UserRegister,
   db: Session = Depends(get_db)
):
  existing_user = (
  db.query(User)
  .filter(User.email == user_data.email)
.first()
)

  if existing_user:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Email is already registered"
    )

  new_user = User(
    full_name=user_data.full_name,
    email=user_data.email,
    password_hash=hash_password(
        user_data.password
    ),
    role=user_data.role
)

  db.add(new_user)
  db.commit()
  db.refresh(new_user)

  return new_user

