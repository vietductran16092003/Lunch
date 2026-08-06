"""Truy vấn bảng coordinator_schedule."""

from ..models import CoordinatorSchedule
from .base import BaseRepository

# Luôn join sang users để có tên người trực; LEFT JOIN phòng trường hợp tài khoản
# bị xoá mà lịch cũ còn sót lại, khi đó user_name là None chứ không mất cả dòng.
SELECT_SCHEDULE = (
    "SELECT cs.date, cs.user_id, cs.created_at, u.name AS user_name "
    "FROM coordinator_schedule cs LEFT JOIN users u ON u.id = cs.user_id"
)


class ScheduleRepository(BaseRepository):

    def find_by_date(self, target_date: str) -> CoordinatorSchedule | None:
        return CoordinatorSchedule.from_row(
            self._fetch_one(f"{SELECT_SCHEDULE} WHERE cs.date = ?", (target_date,))
        )

    def list_range(self, start_date: str, end_date: str) -> list:
        return CoordinatorSchedule.from_rows(
            self._fetch_all(
                f"{SELECT_SCHEDULE} WHERE cs.date BETWEEN ? AND ? ORDER BY cs.date",
                (start_date, end_date),
            )
        )

    def upsert(self, target_date: str, user_id: int, created_at: str):
        """Gán lại ngày đã có người trực là chuyện thường, nên dùng UPSERT thay
        vì bắt tầng trên tự kiểm tra tồn tại rồi chọn INSERT hay UPDATE."""
        self._execute(
            "INSERT INTO coordinator_schedule (date, user_id, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(date) DO UPDATE SET user_id = excluded.user_id",
            (target_date, user_id, created_at),
        )

    def delete(self, target_date: str) -> int:
        return self._execute(
            "DELETE FROM coordinator_schedule WHERE date = ?", (target_date,)
        )
