"""Kênh thông báo thời gian thực (Server-Sent Events).

Vì thông báo ở đây chỉ đi một chiều server -> trình duyệt, SSE là đủ và không cần
thêm thư viện nào ngoài Flask. Nếu sau này cần hai chiều, chỉ phải thay file này
và frontend/realtime.js, phần còn lại của ứng dụng không đổi.
"""

import json
import queue
import threading

# Mỗi trình duyệt đang mở giữ một hàng đợi riêng
_subscribers = []
_lock = threading.Lock()

# Giữ hàng đợi nhỏ: thông báo cũ không còn giá trị, thà bỏ còn hơn dồn bộ nhớ
_QUEUE_MAX = 20


def subscribe():
    """Đăng ký một hàng đợi mới cho một kết nối trình duyệt."""
    q = queue.Queue(maxsize=_QUEUE_MAX)
    with _lock:
        _subscribers.append(q)
    return q


def unsubscribe(q):
    with _lock:
        if q in _subscribers:
            _subscribers.remove(q)


def publish(event_type: str, payload: dict | None = None):
    """Đẩy một sự kiện tới mọi trình duyệt đang mở.

    Không bao giờ ném lỗi ra ngoài: thông báo hỏng không được phép làm chết
    request nghiệp vụ đang chạy.
    """
    message = json.dumps({"type": event_type, "data": payload or {}}, ensure_ascii=False)
    with _lock:
        targets = list(_subscribers)

    for q in targets:
        try:
            q.put_nowait(message)
        except queue.Full:
            # Trình duyệt này đang tụt lại phía sau, bỏ qua sự kiện cho nó
            pass


def stream(q):
    """Sinh chuỗi SSE cho một hàng đợi. Dùng trực tiếp trong Flask Response."""
    # Báo cho trình duyệt biết kết nối đã sẵn sàng
    yield "event: ready\ndata: {}\n\n"
    while True:
        try:
            message = q.get(timeout=25)
            yield f"data: {message}\n\n"
        except queue.Empty:
            # Ping giữ kết nối sống qua proxy/nginx
            yield ": keep-alive\n\n"
