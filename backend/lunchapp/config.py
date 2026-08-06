"""Cấu hình tập trung dưới dạng lớp.

Dùng thuộc tính lớp thay cho biến toàn cục để chỗ nào cần override (test, môi
trường triển khai) chỉ việc gán lại trên Config.
"""

import os
from datetime import date, datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    """Toàn bộ tham số vận hành của ứng dụng."""

    # ===== Hạ tầng =====
    SECRET_KEY = os.environ.get("LUNCH_APP_SECRET", "change-this-secret-key")
    DB_PATH = os.path.join(BASE_DIR, "lunch.db")
    UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

    HOST = "0.0.0.0"
    PORT = 5000
    DEBUG = True

    # ===== Giờ chốt đơn =====
    # Đặt LUNCH_CUTOFF="HH:MM" để đổi mà không phải sửa code.
    ORDER_CUTOFF_HOUR = 10
    ORDER_CUTOFF_MINUTE = 30

    # ===== Tài khoản =====
    ALLOWED_EMAIL_DOMAINS = tuple(
        d.strip().lower()
        for d in os.environ.get("LUNCH_EMAIL_DOMAINS", "fpt.com").split(",")
        if d.strip()
    )
    MIN_PASSWORD_LENGTH = 8
    RESET_TOKEN_TTL_MINUTES = 30
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()

    # ===== Upload ảnh =====
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
    MAX_UPLOAD_BYTES = 4 * 1024 * 1024

    # ===== Tích hợp Grab =====
    GRAB_FETCH_ENABLED = os.environ.get("GRAB_FETCH_ENABLED") == "1"
    GRAB_FETCH_TIMEOUT = 6

    # ----- Giờ chốt -----

    @classmethod
    def load_cutoff_from_env(cls):
        raw = os.environ.get("LUNCH_CUTOFF", "")
        try:
            hour, minute = raw.split(":")
            hour, minute = int(hour), int(minute)
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                cls.ORDER_CUTOFF_HOUR, cls.ORDER_CUTOFF_MINUTE = hour, minute
        except (ValueError, AttributeError):
            pass

    @classmethod
    def cutoff_label(cls) -> str:
        return f"{cls.ORDER_CUTOFF_HOUR:02d}:{cls.ORDER_CUTOFF_MINUTE:02d}"

    @classmethod
    def cutoff_passed_today(cls) -> bool:
        now = datetime.now()
        return (now.hour, now.minute) >= (cls.ORDER_CUTOFF_HOUR, cls.ORDER_CUTOFF_MINUTE)

    @classmethod
    def cutoff_passed_for(cls, target_date: str) -> bool:
        """Giờ chốt chỉ áp cho đơn của chính hôm nay.

        Ngày mai trở đi thì đặt trước lúc nào cũng được, ngày đã qua thì luôn đóng.
        """
        today = date.today().isoformat()
        if target_date > today:
            return False
        if target_date < today:
            return True
        return cls.cutoff_passed_today()

    # ----- Tài khoản -----

    @classmethod
    def email_domain_allowed(cls, email: str) -> bool:
        if "@" not in email:
            return False
        return email.rsplit("@", 1)[1].lower() in cls.ALLOWED_EMAIL_DOMAINS

    @classmethod
    def allowed_domains_label(cls) -> str:
        return ", ".join("@" + d for d in cls.ALLOWED_EMAIL_DOMAINS)

    @classmethod
    def google_enabled(cls) -> bool:
        return bool(cls.GOOGLE_CLIENT_ID)

    # ----- Upload -----

    @classmethod
    def is_allowed_image(cls, filename: str) -> bool:
        if "." not in filename:
            return False
        return filename.rsplit(".", 1)[1].lower() in cls.ALLOWED_IMAGE_EXTENSIONS


Config.load_cutoff_from_env()


class OrderStatus:
    """Vòng đời một đơn hàng."""

    PENDING = "pending"      # nhân viên đang chọn món
    CLOSED = "closed"        # đã chốt, đang thao tác đặt trên Grab
    ORDERED = "ordered"      # đã đặt xong trên Grab, chờ thanh toán
    COMPLETED = "completed"  # người đặt đã xác nhận nhận tiền

    STEPS = [PENDING, CLOSED, ORDERED, COMPLETED]

    LABELS = {
        PENDING: "Đang chọn món",
        CLOSED: "Đã chốt đơn",
        ORDERED: "Đang đặt trên Grab",
        COMPLETED: "Hoàn tất",
    }

    # Các trạng thái mà đơn đã bị khóa, không sửa được nữa
    LOCKED = (CLOSED, ORDERED, COMPLETED)

    @classmethod
    def label(cls, status: str) -> str:
        return cls.LABELS.get(status, status)

    @classmethod
    def index(cls, status: str) -> int:
        try:
            return cls.STEPS.index(status)
        except ValueError:
            return 0
