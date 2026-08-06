"""Tiện ích ngày giờ dùng chung."""

from datetime import date, datetime


class Clock:
    """Gom mọi chỗ đọc thời gian vào một nơi, để test dễ thay thế."""

    @staticmethod
    def today() -> str:
        return date.today().isoformat()

    @staticmethod
    def now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def parse_date(value) -> str | None:
        """Nhận chuỗi YYYY-MM-DD, trả về None nếu sai định dạng."""
        try:
            return date.fromisoformat(str(value)).isoformat()
        except (TypeError, ValueError):
            return None

    @classmethod
    def date_or_today(cls, value) -> str:
        return cls.parse_date(value) or cls.today()

    @classmethod
    def is_past(cls, target_date: str) -> bool:
        return target_date < cls.today()
