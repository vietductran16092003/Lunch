"""Truy vấn bảng deadline_config — giờ chốt đơn riêng theo từng ngày."""

from .base import BaseRepository


class DeadlineRepository(BaseRepository):

    def find_by_date(self, target_date: str):
        return self._fetch_one(
            "SELECT date, cutoff, auto_lock, updated_at FROM deadline_config WHERE date = ?",
            (target_date,),
        )

    def upsert(self, target_date: str, cutoff: str, auto_lock: bool, updated_at: str):
        """Mỗi ngày chỉ có một cấu hình nên ghi đè thẳng theo khoá chính."""
        self._execute(
            "INSERT INTO deadline_config (date, cutoff, auto_lock, updated_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(date) DO UPDATE SET "
            "cutoff = excluded.cutoff, auto_lock = excluded.auto_lock, "
            "updated_at = excluded.updated_at",
            (target_date, cutoff, 1 if auto_lock else 0, updated_at),
        )

    def delete(self, target_date: str) -> int:
        """Xoá cấu hình riêng để ngày đó quay về giờ mặc định của hệ thống."""
        return self._execute("DELETE FROM deadline_config WHERE date = ?", (target_date,))
