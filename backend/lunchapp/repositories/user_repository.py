"""Truy vấn bảng users."""

from ..models import User
from .base import BaseRepository


class UserRepository(BaseRepository):

    def find_by_id(self, user_id) -> User | None:
        return User.from_row(self._fetch_one("SELECT * FROM users WHERE id = ?", (user_id,)))

    def find_by_email(self, email: str) -> User | None:
        return User.from_row(
            self._fetch_one("SELECT * FROM users WHERE email = ?", (email,))
        )

    def find_by_reset_token(self, token: str) -> User | None:
        return User.from_row(
            self._fetch_one("SELECT * FROM users WHERE reset_token = ?", (token,))
        )

    def find_primary_admin(self) -> User | None:
        return User.from_row(
            self._fetch_one("SELECT * FROM users WHERE is_admin = 1 ORDER BY id LIMIT 1")
        )

    def email_exists(self, email: str) -> bool:
        return self._fetch_one("SELECT id FROM users WHERE email = ?", (email,)) is not None

    def create(self, name: str, email: str, password_hash: str,
               is_admin: bool = False, google_sub: str | None = None) -> User:
        new_id = self._insert(
            "INSERT INTO users (name, email, password, is_admin, google_sub) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, email, password_hash, 1 if is_admin else 0, google_sub),
        )
        return self.find_by_id(new_id)

    def update_password(self, user_id, password_hash: str):
        self._execute("UPDATE users SET password = ? WHERE id = ?", (password_hash, user_id))

    def update_google_sub(self, user_id, google_sub: str):
        self._execute("UPDATE users SET google_sub = ? WHERE id = ?", (google_sub, user_id))

    def set_reset_token(self, user_id, token: str, expires: str):
        self._execute(
            "UPDATE users SET reset_token = ?, reset_expires = ? WHERE id = ?",
            (token, expires, user_id),
        )

    def clear_reset_token_and_set_password(self, user_id, password_hash: str):
        self._execute(
            "UPDATE users SET password = ?, reset_token = NULL, reset_expires = NULL "
            "WHERE id = ?",
            (password_hash, user_id),
        )

    def update_payment_info(self, user_id, phone: str | None, qr_image_url: str | None):
        self._execute(
            "UPDATE users SET phone = ?, qr_image_url = ? WHERE id = ?",
            (phone or None, qr_image_url or None, user_id),
        )
