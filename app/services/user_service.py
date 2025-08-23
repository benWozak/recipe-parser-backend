from sqlalchemy.orm import Session
from typing import Optional
from app.models.user import User
from app.schemas.user import UserUpdate

class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_user_by_clerk_id(self, clerk_user_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.clerk_user_id == clerk_user_id).first()

    def update_user(self, user_id: str, user_update: UserUpdate) -> Optional[User]:
        user = self.get_user_by_id(user_id)
        if not user:
            return None

        update_data = user_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        self.db.commit()
        self.db.refresh(user)
        return user