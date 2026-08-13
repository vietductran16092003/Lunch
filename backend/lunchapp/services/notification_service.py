"""Trung tâm thông báo: lưu lại các thông báo (không chỉ đẩy realtime rồi mất),
để người dùng mở lại trang vẫn xem được thông báo cũ chưa đọc."""


class NotificationService:
    def __init__(self, notification_repository, event_broker):
        self.notifications = notification_repository
        self.events = event_broker

    def notify(self, type: str, title: str, message: str | None = None,
               target_user_id=None, target_role: str | None = None) -> dict:
        """Ghi một thông báo mới rồi đẩy realtime cho mọi trình duyệt đang mở —
        phía nhận tự lọc thông báo nào thuộc về mình dựa trên target_user_id/
        target_role đi kèm."""
        notification_id = self.notifications.create(
            type, title, message, target_user_id=target_user_id, target_role=target_role,
        )
        payload = {
            "id": notification_id, "type": type, "title": title, "message": message,
            "target_user_id": target_user_id, "target_role": target_role,
            "is_read": False,
        }
        self.events.publish("notification_created", payload)
        return payload

    def list_for_user(self, user_id, roles: list, limit: int = 30) -> dict:
        """Thông báo dành cho người này: gửi riêng cho họ, cho vai trò họ mang, hoặc gửi chung."""
        items = self.notifications.list_for_user(user_id, roles, limit)
        return {
            "notifications": [n.to_dict() for n in items],
            "unread_count": self.notifications.unread_count(user_id, roles),
        }

    def unread_count(self, user_id, roles: list) -> dict:
        """Số thông báo chưa đọc — dùng cho chấm đỏ trên chuông thông báo."""
        return {"unread_count": self.notifications.unread_count(user_id, roles)}

    def mark_read(self, notification_id, user_id) -> dict:
        """Đánh dấu đã đọc — theo từng người xem, không phải theo thông báo."""
        self.notifications.mark_read(notification_id, user_id)
        return {"status": "read"}

    def mark_all_read(self, user_id, roles: list) -> dict:
        """Đánh dấu đã đọc hết mọi thông báo hiện đang thấy được của người này."""
        self.notifications.mark_all_read(user_id, roles)
        return {"status": "read"}
