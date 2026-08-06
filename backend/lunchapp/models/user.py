"""Thực thể người dùng."""

from .base import BaseModel


class User(BaseModel):
    FIELDS = ("id", "name", "email", "is_admin")

    def __init__(self, id, name, email, is_admin=False, password=None, phone=None,
                 qr_image_url=None, google_sub=None, reset_token=None, reset_expires=None):
        self.id = id
        self.name = name
        self.email = email
        self.is_admin = bool(is_admin)
        self.password = password
        self.phone = phone
        self.qr_image_url = qr_image_url
        self.google_sub = google_sub
        self.reset_token = reset_token
        self.reset_expires = reset_expires

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
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
        )

    def has_hashed_password(self) -> bool:
        """werkzeug ghi mật khẩu dạng "method$salt$hash"."""
        return bool(self.password) and self.password.count("$") >= 2

    def to_payment_info(self) -> dict:
        """Thông tin để nhân viên chuyển khoản cho người đứng ra đặt."""
        return {"name": self.name, "phone": self.phone, "qr_image_url": self.qr_image_url}
