from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import UserOut, UserUpdate
from ..security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current)


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UserUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    if payload.password is not None:
        current.password_hash = hash_password(payload.password)
    if payload.telegram_chat_id is not None:
        current.telegram_chat_id = payload.telegram_chat_id
    if payload.telegram_enabled is not None:
        current.telegram_enabled = payload.telegram_enabled
    db.commit()
    db.refresh(current)
    return UserOut.model_validate(current)
