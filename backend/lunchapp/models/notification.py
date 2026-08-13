"""Thực thể một thông báo trong trung tâm thông báo."""

from .base import BaseModel


class Notification(BaseModel):
    FIELDS = ("id", "type", "title", "message", "created_at")

    def __init__(self, id=None, type=None, title=None, message=None,
                 target_user_id=None, target_role=None, created_at=None, is_read=False):
        self.id = id
        self.type = type
        self.title = title
        self.message = message
        # Cả hai đều None nghĩa là gửi cho mọi người
        self.target_user_id = target_user_id
        self.target_role = target_role
        self.created_at = created_at
        self.is_read = bool(is_read)

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        return cls(
            id=cls.column(row, "id"),
            type=cls.column(row, "type"),
            title=cls.column(row, "title"),
            message=cls.column(row, "message"),
            target_user_id=cls.column(row, "target_user_id"),
            target_role=cls.column(row, "target_role"),
            created_at=cls.column(row, "created_at"),
            is_read=bool(cls.column(row, "is_read", 0)),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "target_user_id": self.target_user_id,
            "target_role": self.target_role,
            "created_at": self.created_at,
            "is_read": self.is_read,
        }
