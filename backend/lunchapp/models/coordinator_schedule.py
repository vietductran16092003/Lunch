"""Thực thể một ngày trực trong lịch điều phối."""

from .base import BaseModel


class CoordinatorSchedule(BaseModel):
    # user_name lấy từ join sang users; giữ trong FIELDS để frontend khỏi phải
    # gọi thêm một vòng chỉ để đổi id thành tên.
    FIELDS = ("date", "user_id", "user_name")

    def __init__(self, date, user_id, user_name=None, created_at=None):
        self.date = date
        self.user_id = user_id
        self.user_name = user_name
        self.created_at = created_at

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        return cls(
            date=cls.column(row, "date"),
            user_id=cls.column(row, "user_id"),
            user_name=cls.column(row, "user_name"),
            created_at=cls.column(row, "created_at"),
        )
