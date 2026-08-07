"""Thực thể bình chọn quán ăn (Phase 4)."""

from .base import BaseModel


class Poll(BaseModel):
    FIELDS = ("id", "question", "poll_date", "created_by", "closed")

    def __init__(self, id=None, question=None, poll_date=None, created_by=None,
                 closed=False, options=None):
        self.id = id
        self.question = question
        self.poll_date = poll_date
        self.created_by = created_by
        self.closed = bool(closed)
        # [{"id", "label", "votes"}], gắn thêm sau khi đọc kết quả
        self.options = options or []

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        return cls(
            id=cls.column(row, "id"),
            question=cls.column(row, "question"),
            poll_date=cls.column(row, "poll_date"),
            created_by=cls.column(row, "created_by"),
            closed=cls.column(row, "closed", 0),
        )

    def to_dict(self, voted_option_id=None) -> dict:
        return {
            "id": self.id,
            "question": self.question,
            "poll_date": self.poll_date,
            "closed": self.closed,
            "options": self.options,
            "total_votes": sum(o["votes"] for o in self.options),
            "voted_option_id": voted_option_id,
        }
