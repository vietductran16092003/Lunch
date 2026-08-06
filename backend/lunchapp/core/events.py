"""Kênh thông báo thời gian thực (Server-Sent Events).

Thông báo chỉ đi một chiều server -> trình duyệt nên SSE là đủ, không cần thêm
thư viện. Muốn đổi sang WebSocket thì chỉ phải thay lớp này và file
frontend/js/core/RealtimeClient.js.
"""

import json
import queue
import threading


class EventBroker:
    """Phát sự kiện tới mọi trình duyệt đang mở."""

    QUEUE_MAX = 20
    KEEPALIVE_SECONDS = 25

    def __init__(self):
        self._subscribers = []
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        q = queue.Queue(maxsize=self.QUEUE_MAX)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    def publish(self, event_type: str, payload: dict | None = None):
        """Không bao giờ ném lỗi ra ngoài: thông báo hỏng không được làm chết
        request nghiệp vụ đang chạy."""
        message = json.dumps(
            {"type": event_type, "data": payload or {}}, ensure_ascii=False
        )
        with self._lock:
            targets = list(self._subscribers)

        for q in targets:
            try:
                q.put_nowait(message)
            except queue.Full:
                # Trình duyệt này đang tụt lại phía sau, bỏ qua sự kiện cho nó
                pass

    def stream(self, q: queue.Queue):
        """Sinh chuỗi SSE cho một hàng đợi. Dùng trực tiếp trong Flask Response."""
        yield "event: ready\ndata: {}\n\n"
        while True:
            try:
                message = q.get(timeout=self.KEEPALIVE_SECONDS)
                yield f"data: {message}\n\n"
            except queue.Empty:
                yield ": keep-alive\n\n"
