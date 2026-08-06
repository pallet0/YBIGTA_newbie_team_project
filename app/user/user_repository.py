from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.user.user_schema import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user_by_email(self, email: str) -> Optional[User]:
        result = self.db.execute(
            text("SELECT email, password, username FROM users WHERE email = :email"),
            {"email": email}
        ).fetchone()

        if result is None:
            return None
        return User(email=result.email, password=result.password, username=result.username)

    def save_user(self, user: User) -> User:
        existing = self.get_user_by_email(user.email)

        if existing:
            self.db.execute(
                text("UPDATE users SET password = :password, username = :username WHERE email = :email"),
                {"password": user.password, "username": user.username, "email": user.email}
            )
        else:
            self.db.execute(
                text("INSERT INTO users (email, password, username) VALUES (:email, :password, :username)"),
                {"email": user.email, "password": user.password, "username": user.username}
            )

        self.db.commit()
        return user

    def delete_user(self, user: User) -> User:
        self.db.execute(
            text("DELETE FROM users WHERE email = :email"),
            {"email": user.email}
        )
        self.db.commit()
        return user