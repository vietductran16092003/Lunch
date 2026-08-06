"""Giờ chốt đơn theo ngày và quy tắc tự khoá (mã 4.1).

Trước đây giờ chốt là một hằng số duy nhất trong Config. Từ giờ mỗi ngày có thể
đặt giờ riêng — hôm nào ăn sớm thì chốt sớm — còn ngày nào không cấu hình thì
vẫn dùng giờ mặc định như cũ, nên hành vi hiện tại không đổi.
"""

import re

from ..config import Config
from ..core.dates import Clock
from ..core.errors import ValidationError

CUTOFF_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class DeadlineService:

    def __init__(self, deadline_repository, config=Config, clock=Clock, event_broker=None):
        self.deadlines = deadline_repository
        self.config = config
        self.clock = clock
        self.events = event_broker

    # ===== Đọc =====

    def cutoff_for(self, target_date: str) -> str:
        """Giờ chốt áp dụng cho một ngày: ưu tiên cấu hình riêng, không có thì lấy mặc định."""
        row = self.deadlines.find_by_date(target_date)
        if row and row["cutoff"]:
            return row["cutoff"]
        return self.config.cutoff_label()

    def auto_lock_for(self, target_date: str) -> bool:
        row = self.deadlines.find_by_date(target_date)
        if row is None:
            return True
        return bool(row["auto_lock"])

    def is_locked(self, target_date: str) -> bool:
        """Ngày này đã quá giờ chốt chưa.

        Tắt auto_lock thì ngày đó không bao giờ tự khoá — người điều phối chủ
        động bấm chốt tay. Ngày đã qua thì luôn coi là khoá.
        """
        today = self.clock.today()
        if target_date > today:
            return False
        if target_date < today:
            return True
        if not self.auto_lock_for(target_date):
            return False
        return self._passed_today(self.cutoff_for(target_date))

    def describe(self, target_date=None) -> dict:
        target_date = self.clock.date_or_today(target_date)
        row = self.deadlines.find_by_date(target_date)

        return {
            "date": target_date,
            "cutoff": self.cutoff_for(target_date),
            "source": "custom" if row and row["cutoff"] else "default",
            "auto_lock": self.auto_lock_for(target_date),
            "locked": self.is_locked(target_date),
            "default_cutoff": self.config.cutoff_label(),
            "is_today": target_date == self.clock.today(),
        }

    # ===== Ghi =====

    def configure(self, data: dict) -> dict:
        target_date = self.clock.parse_date(data.get("date"))
        if target_date is None:
            raise ValidationError("Ngày không hợp lệ, cần định dạng YYYY-MM-DD")

        cutoff = (data.get("cutoff") or "").strip()
        if not CUTOFF_PATTERN.match(cutoff):
            raise ValidationError("Giờ chốt không hợp lệ, cần định dạng HH:MM")

        # Không cho đặt giờ chốt cho ngày đã qua: sửa cũng không còn tác dụng gì
        if self.clock.is_past(target_date):
            raise ValidationError(f"Ngày {target_date} đã qua, không đổi giờ chốt được")

        auto_lock = data.get("auto_lock", True)
        self.deadlines.upsert(target_date, cutoff, bool(auto_lock), self.clock.now())

        result = self.describe(target_date)
        if self.events:
            self.events.publish("deadline_updated", {
                "date": target_date, "cutoff": cutoff, "auto_lock": bool(auto_lock),
            })
        return result

    def reset(self, target_date: str) -> dict:
        """Bỏ cấu hình riêng, trả ngày đó về giờ mặc định."""
        target_date = self.clock.date_or_today(target_date)
        self.deadlines.delete(target_date)
        if self.events:
            self.events.publish("deadline_updated", {"date": target_date, "reset": True})
        return self.describe(target_date)

    # ===== Nội bộ =====

    def _passed_today(self, cutoff: str) -> bool:
        from datetime import datetime

        hour, minute = (int(part) for part in cutoff.split(":"))
        now = datetime.now()
        return (now.hour, now.minute) >= (hour, minute)
