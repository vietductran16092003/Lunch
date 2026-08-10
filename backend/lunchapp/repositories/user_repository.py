"""Truy vấn bảng users và user_roles."""

from ..core.roles import Role
from ..models import User
from .base import BaseRepository

# Gộp vai trò ngay trong câu SELECT: một lượt đi database là có đủ User, khỏi
# phải bắn thêm N truy vấn khi liệt kê danh sách người dùng.
ROLES_COLUMN = (
    "(SELECT GROUP_CONCAT(ur.role) FROM user_roles ur WHERE ur.user_id = users.id) AS roles"
)
SELECT_USER = f"SELECT users.*, {ROLES_COLUMN} FROM users"


class UserRepository(BaseRepository):

    def find_by_id(self, user_id) -> User | None:
        return User.from_row(
            self._fetch_one(f"{SELECT_USER} WHERE users.id = ?", (user_id,))
        )

    def find_by_email(self, email: str) -> User | None:
        return User.from_row(
            self._fetch_one(f"{SELECT_USER} WHERE users.email = ?", (email,))
        )

    def find_by_reset_token(self, token: str) -> User | None:
        return User.from_row(
            self._fetch_one(f"{SELECT_USER} WHERE users.reset_token = ?", (token,))
        )

    def find_primary_admin(self) -> User | None:
        return User.from_row(
            self._fetch_one(f"{SELECT_USER} WHERE users.is_admin = 1 ORDER BY users.id LIMIT 1")
        )

    def list_all(self) -> list:
        return User.from_rows(self._fetch_all(f"{SELECT_USER} ORDER BY users.id"))

    def email_exists(self, email: str) -> bool:
        return self._fetch_one("SELECT id FROM users WHERE email = ?", (email,)) is not None

    def create(self, name: str, email: str, password_hash: str,
               is_admin: bool = False, google_sub: str | None = None) -> User:
        new_id = self._insert(
            "INSERT INTO users (name, email, password, is_admin, google_sub) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, email, password_hash, 1 if is_admin else 0, google_sub),
        )
        # Người mới luôn phải có vai trò ngay, nếu không họ sẽ là tài khoản
        # "không quyền gì" và không qua nổi require_role đầu tiên.
        self.replace_roles(new_id, Role.for_admin_flag(is_admin))
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

    # ===== Vai trò =====

    def roles_of(self, user_id) -> list:
        rows = self._fetch_all(
            "SELECT role FROM user_roles WHERE user_id = ?", (user_id,)
        )
        return Role.sort([row["role"] for row in rows])

    def replace_roles(self, user_id, roles) -> list:
        """Ghi đè trọn bộ vai trò trong một giao dịch.

        Xoá rồi chèn lại gọn hơn là so sánh sai khác, và vì nằm chung một
        session(commit=True) nên không có khoảnh khắc user bị mất sạch quyền.
        Cột users.is_admin được đồng bộ ngay tại đây — đó là chỗ DUY NHẤT giữ hai
        nguồn dữ liệu này khớp nhau.
        """
        clean = Role.sort(roles)
        with self.db.session(commit=True) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
            cursor.executemany(
                "INSERT INTO user_roles (user_id, role) VALUES (?, ?)",
                [(user_id, role) for role in clean],
            )
            cursor.execute(
                "UPDATE users SET is_admin = ? WHERE id = ?",
                (1 if Role.ADMIN in clean else 0, user_id),
            )
        return clean

    def delete(self, user_id):
        with self.db.session(commit=True) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))

    def has_orders(self, user_id) -> bool:
        return self._fetch_one(
            "SELECT 1 FROM orders WHERE user_id = ?", (user_id,)
        ) is not None

    def count_with_role(self, role: str) -> int:
        row = self._fetch_one(
            "SELECT COUNT(*) AS total FROM user_roles WHERE role = ?", (role,)
        )
        return row["total"] if row else 0

    def has_role(self, user_id, role: str) -> bool:
        return self._fetch_one(
            "SELECT 1 FROM user_roles WHERE user_id = ? AND role = ?", (user_id, role)
        ) is not None
