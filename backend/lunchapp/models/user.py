"""Thực thể người dùng."""

from ..core.roles import Role
from .base import BaseModel

_MISSING = object()


class User(BaseModel):
    # Vẫn trả `is_admin` cho frontend cũ, đồng thời thêm `roles` cho mô hình mới.
    FIELDS = ("id", "name", "email", "is_admin", "roles")

    def __init__(self, id, name, email, is_admin=False, password=None, phone=None,
                 qr_image_url=None, google_sub=None, reset_token=None, reset_expires=None,
                 roles=None):
        self.id = id
        self.name = name
        self.email = email
        # Không truyền roles thì suy từ cờ is_admin cũ, để mọi chỗ dựng User bằng
        # tay (test, code cũ) vẫn có danh sách vai trò hợp lý.
        self.roles = Role.sort(roles) if roles is not None else Role.for_admin_flag(is_admin)
        self.password = password
        self.phone = phone
        self.qr_image_url = qr_image_url
        self.google_sub = google_sub
        self.reset_token = reset_token
        self.reset_expires = reset_expires

    @property
    def is_admin(self) -> bool:
        """Suy từ vai trò, không đọc cột is_admin nữa — cột đó chỉ còn là bản sao."""
        return Role.ADMIN in self.roles

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None

        # Câu SELECT có kèm cột `roles` (chuỗi GROUP_CONCAT) thì dùng nó; câu nào
        # không lấy cột đó — ví dụ join từ repository khác — thì quay về is_admin.
        raw_roles = cls.column(row, "roles", _MISSING)
        if raw_roles is _MISSING:
            roles = None
        elif isinstance(raw_roles, str):
            roles = Role.clean_many(raw_roles.split(","))
        elif raw_roles is None:
            roles = []
        else:
            roles = Role.clean_many(raw_roles)

        return cls(
            id=cls.column(row, "id"),
            name=cls.column(row, "name"),
            email=cls.column(row, "email"),
            is_admin=cls.column(row, "is_admin", 0),
            password=cls.column(row, "password"),
            phone=cls.column(row, "phone"),
            qr_image_url=cls.column(row, "qr_image_url"),
            google_sub=cls.column(row, "google_sub"),
            reset_token=cls.column(row, "reset_token"),
            reset_expires=cls.column(row, "reset_expires"),
            roles=roles,
        )

    # ===== Vai trò =====

    def has_role(self, role) -> bool:
        return role in self.roles

    def has_any(self, *roles) -> bool:
        """Không truyền vai trò nào thì coi như không đòi hỏi gì — luôn đúng."""
        if not roles:
            return True
        return any(role in self.roles for role in roles)

    def role_labels(self) -> list:
        return [Role.label(role) for role in self.roles]

    def has_hashed_password(self) -> bool:
        """werkzeug ghi mật khẩu dạng "method$salt$hash"."""
        return bool(self.password) and self.password.count("$") >= 2

    def to_payment_info(self) -> dict:
        """Thông tin để nhân viên chuyển khoản cho người đứng ra đặt."""
        return {"name": self.name, "phone": self.phone, "qr_image_url": self.qr_image_url}

    def to_directory_entry(self) -> dict:
        """Bản rút gọn dùng cho màn hình quản lý phân quyền."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "roles": list(self.roles),
            # Đã bấm "Quên mật khẩu", đang chờ quản trị viên duyệt
            "password_reset_pending": bool(self.reset_token),
        }
