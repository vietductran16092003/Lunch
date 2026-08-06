"""Nghiệp vụ lịch trực điều phối luân phiên."""

from ..core.dates import Clock
from ..core.errors import NotFoundError, ValidationError
from ..core.roles import Role

# Nhìn trước 2 tuần là vừa đủ để mọi người biết đến lượt mình mà không phải cuộn
# một danh sách dài; frontend muốn khác thì truyền from/to.
DEFAULT_WINDOW_DAYS = 13


class ScheduleService:
    """Ai lo đặt cơm ngày nào.

    Service chỉ làm việc với chuỗi ngày YYYY-MM-DD và không biết gì về Flask.
    """

    def __init__(self, schedule_repository, user_repository, clock=Clock):
        self.schedules = schedule_repository
        self.users = user_repository
        self.clock = clock

    # ===== Đọc =====

    def coordinator_for(self, target_date=None):
        """Trả về User phụ trách ngày đó, None nếu chưa ai được gán."""
        entry = self.schedules.find_by_date(self._require_date(target_date))
        if entry is None or entry.user_id is None:
            return None
        return self.users.find_by_id(entry.user_id)

    def range(self, date_from=None, date_to=None) -> list:
        start, end = self._window(date_from, date_to)
        return self.schedules.list_range(start, end)

    def overview(self, date_from=None, date_to=None) -> dict:
        """Gói sẵn payload cho màn hình lịch: dải ngày + ai trực hôm nay."""
        start, end = self._window(date_from, date_to)
        today = self.clock.today()
        today_entry = self.schedules.find_by_date(today)

        return {
            "schedule": [entry.to_dict() for entry in self.schedules.list_range(start, end)],
            "today": today,
            "today_coordinator": (
                {"user_id": today_entry.user_id, "user_name": today_entry.user_name}
                if today_entry else None
            ),
        }

    # ===== Ghi =====

    def assign(self, target_date, user_id) -> dict:
        target_date = self._require_date(target_date)

        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            raise ValidationError("Thiếu hoặc sai người được phân công")

        user = self.users.find_by_id(user_id)
        if user is None:
            raise NotFoundError("Không tìm thấy người dùng")

        # Chặn ngay từ đây thay vì để lúc chạy mới lộ ra: người không có vai trò
        # điều phối thì không có quyền chốt đơn, gán vào lịch chỉ gây kẹt.
        if not user.has_role(Role.COORDINATOR):
            raise ValidationError(
                f"{user.name} chưa có vai trò {Role.label(Role.COORDINATOR).lower()}"
            )

        self.schedules.upsert(target_date, user.id, self.clock.now())
        return {"date": target_date, "user_id": user.id, "user_name": user.name}

    def unassign(self, target_date) -> dict:
        target_date = self._require_date(target_date)
        if not self.schedules.delete(target_date):
            raise NotFoundError("Ngày này chưa được phân công")
        return {"status": "deleted"}

    # ===== Tiện ích ngày =====

    def _require_date(self, value) -> str:
        """Ở đây không dùng date_or_today: ghi nhầm vào hôm nay vì gõ sai định
        dạng là lỗi âm thầm, thà báo 400 cho rõ."""
        parsed = self.clock.parse_date(value)
        if parsed is None:
            raise ValidationError("Ngày không hợp lệ, cần định dạng YYYY-MM-DD")
        return parsed

    def _window(self, date_from, date_to) -> tuple:
        from datetime import date, timedelta

        start = self.clock.parse_date(date_from) or self.clock.today()
        end = self.clock.parse_date(date_to)
        if end is None:
            end = (
                date.fromisoformat(start) + timedelta(days=DEFAULT_WINDOW_DAYS)
            ).isoformat()
        # Người dùng đảo ngược from/to thì hiểu ý thay vì trả danh sách rỗng
        if end < start:
            start, end = end, start
        return start, end
