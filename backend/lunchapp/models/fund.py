"""Thực thể một dòng sổ quỹ (nạp/rút)."""

from .base import BaseModel


class FundTransaction(BaseModel):
    FIELDS = ("id", "type", "amount", "user_id", "user_name", "note", "created_at", "month")

    def __init__(self, id=None, type=None, amount=0, user_id=None, user_name=None,
                 note=None, created_at=None, month=None):
        self.id = id
        # "topup" (nạp), "deduct" (rút), "order_payment" (trả đơn bằng quỹ) hoặc "dues" (góp quỹ tháng)
        self.type = type
        self.amount = amount
        self.user_id = user_id
        self.user_name = user_name
        self.note = note
        self.created_at = created_at
        # Chỉ có giá trị ở dòng type="dues", dạng "YYYY-MM"
        self.month = month

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        return cls(
            id=cls.column(row, "id"),
            type=cls.column(row, "type"),
            amount=cls.column(row, "amount", 0),
            user_id=cls.column(row, "user_id"),
            user_name=cls.column(row, "user_name"),
            note=cls.column(row, "note"),
            created_at=cls.column(row, "created_at"),
            month=cls.column(row, "month"),
        )
