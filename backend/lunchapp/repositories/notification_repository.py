"""Truy vấn bảng notifications và notification_reads."""

from ..models import Notification
from .base import BaseRepository

# Một thông báo hiện ra với một người nếu: gửi đích danh họ, gửi theo vai trò
# họ đang mang, hoặc gửi cho mọi người (cả hai cột target đều NULL).
_VISIBLE_WHERE = """
    (notifications.target_user_id = ?
     OR notifications.target_role IN ({role_placeholders})
     OR (notifications.target_user_id IS NULL AND notifications.target_role IS NULL))
"""

_SELECT_WITH_READ = """
    SELECT notifications.*,
           CASE WHEN notification_reads.user_id IS NULL THEN 0 ELSE 1 END AS is_read
    FROM notifications
    LEFT JOIN notification_reads
        ON notification_reads.notification_id = notifications.id
        AND notification_reads.user_id = ?
"""


class NotificationRepository(BaseRepository):
    """CRUD cho notifications + notification_reads (đã đọc theo từng người xem)."""

    def create(self, type: str, title: str, message: str | None,
               target_user_id=None, target_role: str | None = None,
               created_at: str | None = None) -> int:
        return self._insert(
            "INSERT INTO notifications "
            "(type, title, message, target_user_id, target_role, created_at) "
            "VALUES (?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))",
            (type, title, message, target_user_id, target_role, created_at),
        )

    def list_for_user(self, user_id, roles: list, limit: int = 30) -> list:
        role_placeholders = ",".join("?" * len(roles)) if roles else "''"
        where = _VISIBLE_WHERE.format(role_placeholders=role_placeholders)
        rows = self._fetch_all(
            f"{_SELECT_WITH_READ} WHERE {where} "
            "ORDER BY notifications.id DESC LIMIT ?",
            (user_id, user_id, *roles, limit),
        )
        return Notification.from_rows(rows)

    def unread_count(self, user_id, roles: list) -> int:
        role_placeholders = ",".join("?" * len(roles)) if roles else "''"
        where = _VISIBLE_WHERE.format(role_placeholders=role_placeholders)
        row = self._fetch_one(
            f"SELECT COUNT(*) AS total FROM notifications "
            f"LEFT JOIN notification_reads "
            f"  ON notification_reads.notification_id = notifications.id "
            f"  AND notification_reads.user_id = ? "
            f"WHERE {where} AND notification_reads.user_id IS NULL",
            (user_id, user_id, *roles),
        )
        return row["total"] if row else 0

    def mark_read(self, notification_id, user_id):
        self._execute(
            "INSERT OR IGNORE INTO notification_reads (notification_id, user_id) "
            "VALUES (?, ?)",
            (notification_id, user_id),
        )

    def mark_all_read(self, user_id, roles: list):
        role_placeholders = ",".join("?" * len(roles)) if roles else "''"
        where = _VISIBLE_WHERE.format(role_placeholders=role_placeholders)
        self._execute(
            f"INSERT OR IGNORE INTO notification_reads (notification_id, user_id) "
            f"SELECT notifications.id, ? FROM notifications WHERE {where}",
            (user_id, user_id, *roles),
        )
