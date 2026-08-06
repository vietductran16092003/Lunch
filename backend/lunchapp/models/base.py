"""Lớp cha cho mọi thực thể."""

import sqlite3


class BaseModel:
    """Thực thể dựng từ một dòng SQLite.

    Lớp con khai báo FIELDS và tự cài __init__; ở đây chỉ lo phần dùng chung là
    đọc an toàn một cột có thể chưa tồn tại và đổi sang dict cho JSON.
    """

    FIELDS: tuple = ()

    @staticmethod
    def column(row, key, default=None):
        """Đọc một cột mà không vỡ khi câu SELECT không lấy cột đó."""
        if row is None:
            return default
        if isinstance(row, sqlite3.Row):
            return row[key] if key in row.keys() else default
        return row.get(key, default)

    @classmethod
    def from_row(cls, row):
        raise NotImplementedError

    @classmethod
    def from_rows(cls, rows) -> list:
        return [cls.from_row(r) for r in rows or []]

    def to_dict(self) -> dict:
        return {name: getattr(self, name) for name in self.FIELDS}

    def __repr__(self) -> str:
        inner = ", ".join(f"{name}={getattr(self, name)!r}" for name in self.FIELDS[:3])
        return f"<{type(self).__name__} {inner}>"
