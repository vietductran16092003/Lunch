"""Giới hạn tần suất gọi API theo IP, lưu trong bộ nhớ tiến trình.

Không dùng thư viện ngoài vì quy mô app này chạy một tiến trình duy nhất; nhiều
tiến trình/server thì phải chuyển sang lưu đếm ở Redis hoặc tương tự.
"""

import threading
import time
from functools import wraps

from flask import request

from .errors import AppError


class RateLimitError(AppError):
    status_code = 429


class RateLimiter:
    def __init__(self):
        self._hits = {}
        self._lock = threading.Lock()

    def _key(self, bucket: str) -> str:
        return f"{bucket}:{request.remote_addr or 'unknown'}"

    def check(self, bucket: str, max_calls: int, window_seconds: int):
        key = self._key(bucket)
        now = time.time()

        with self._lock:
            timestamps = [t for t in self._hits.get(key, []) if now - t < window_seconds]
            if len(timestamps) >= max_calls:
                raise RateLimitError(
                    "Bạn thao tác quá nhanh, vui lòng thử lại sau ít phút",
                    payload={"retry_after_seconds": window_seconds},
                )
            timestamps.append(now)
            self._hits[key] = timestamps


limiter = RateLimiter()


def rate_limit(bucket: str, max_calls: int, window_seconds: int):
    """Áp cho một route: `@rate_limit("login", 10, 60)` = tối đa 10 lần/phút/IP."""

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            limiter.check(bucket, max_calls, window_seconds)
            return f(*args, **kwargs)

        return wrapper

    return decorator
