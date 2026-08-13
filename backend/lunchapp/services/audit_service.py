"""Ghi vết các thao tác đáng tra lại sau này (ai claim/gỡ ngày, xoá món/quán...).

Chỉ ghi, không đọc lại trong luồng nghiệp vụ chính — audit_log tồn tại cho con
người tra cứu khi có tranh chấp, không phải để service khác dựa vào.
"""


class AuditService:
    """Ghi vết ai làm gì — dùng optional (`self.audit`) ở CollectorService/
    OrderService, tất cả lời gọi đều bọc `if self.audit:` để service cũ/test
    không truyền vào vẫn chạy được."""

    def __init__(self, audit_log_repository):
        self.log_repo = audit_log_repository

    def log(self, actor_id, action: str, entity_type: str, entity_id=None, details: str | None = None):
        """Ghi một dòng vết — action là tên sự kiện ngắn gọn (vd "date_owner_claimed")."""
        self.log_repo.record(actor_id, action, entity_type, entity_id, details)

    def history_for(self, entity_type: str, entity_id) -> list:
        """Lịch sử vết của một đối tượng, kèm tên người thực hiện (join users)."""
        rows = self.log_repo.list_for_entity(entity_type, entity_id)
        return [
            {
                "id": r["id"],
                "actor_id": r["actor_id"],
                "actor_name": r["actor_name"],
                "action": r["action"],
                "details": r["details"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]
