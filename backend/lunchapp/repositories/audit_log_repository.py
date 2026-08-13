"""Truy vấn bảng audit_log — sổ ghi vết chỉ thêm dòng, không sửa/xoá."""

from .base import BaseRepository


class AuditLogRepository(BaseRepository):

    def record(self, actor_id, action: str, entity_type: str, entity_id=None, details=None):
        """Ghi một dòng vết mới — chỉ thêm, không có update/delete cho bảng này."""
        self._insert(
            "INSERT INTO audit_log (actor_id, action, entity_type, entity_id, details) "
            "VALUES (?, ?, ?, ?, ?)",
            (actor_id, action, entity_type, str(entity_id) if entity_id is not None else None, details),
        )

    def list_for_entity(self, entity_type: str, entity_id) -> list:
        """Toàn bộ vết của một đối tượng cụ thể (vd order_date="2026-08-13"), mới nhất trước."""
        return self._fetch_all(
            """
            SELECT audit_log.*, users.name AS actor_name
            FROM audit_log
            LEFT JOIN users ON audit_log.actor_id = users.id
            WHERE entity_type = ? AND entity_id = ?
            ORDER BY audit_log.id DESC
            """,
            (entity_type, str(entity_id)),
        )
