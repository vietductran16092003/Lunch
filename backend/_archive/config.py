"""Cấu hình tập trung cho Lunch App.

Gom các hằng số nghiệp vụ về một chỗ để đổi giờ chốt đơn hay quy tắc upload
không phải đi sửa rải rác trong app.py.
"""

import os

# ===== Giờ chốt đơn tự động =====
# Sau mốc này nhân viên không đặt/sửa/hủy được nữa.
# Đặt biến môi trường LUNCH_CUTOFF="HH:MM" để đổi mà không phải sửa code.
def _read_cutoff(default_hour=10, default_minute=30):
    raw = os.environ.get("LUNCH_CUTOFF", "")
    try:
        hour, minute = raw.split(":")
        hour, minute = int(hour), int(minute)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
    except (ValueError, AttributeError):
        pass
    return default_hour, default_minute


ORDER_CUTOFF_HOUR, ORDER_CUTOFF_MINUTE = _read_cutoff()


def order_cutoff_label() -> str:
    return f"{ORDER_CUTOFF_HOUR:02d}:{ORDER_CUTOFF_MINUTE:02d}"


def order_cutoff_passed() -> bool:
    from datetime import datetime

    now = datetime.now()
    return (now.hour, now.minute) >= (ORDER_CUTOFF_HOUR, ORDER_CUTOFF_MINUTE)


def cutoff_passed_for(target_date: str) -> bool:
    """Giờ chốt chỉ áp cho đơn của chính hôm nay.

    Ngày mai trở đi thì đặt trước lúc nào cũng được, còn ngày đã qua thì luôn
    coi như đã đóng.
    """
    from datetime import date

    today = date.today().isoformat()
    if target_date > today:
        return False
    if target_date < today:
        return True
    return order_cutoff_passed()


def date_is_past(target_date: str) -> bool:
    from datetime import date

    return target_date < date.today().isoformat()


# ===== Vòng đời đơn hàng =====
# pending  -> nhân viên đang chọn món
# closed   -> quản trị viên đã chốt, đang thao tác đặt trên Grab
# ordered  -> đã đặt xong trên Grab, đến lượt nhân viên thanh toán
# completed-> nhân viên đã thanh toán xong
STATUS_PENDING = "pending"
STATUS_CLOSED = "closed"
STATUS_ORDERED = "ordered"
STATUS_COMPLETED = "completed"

ORDER_STEPS = [STATUS_PENDING, STATUS_CLOSED, STATUS_ORDERED, STATUS_COMPLETED]

STATUS_LABELS = {
    STATUS_PENDING: "Đang chọn món",
    STATUS_CLOSED: "Đã chốt đơn",
    STATUS_ORDERED: "Đang đặt trên Grab",
    STATUS_COMPLETED: "Hoàn tất",
}


def status_index(status: str) -> int:
    try:
        return ORDER_STEPS.index(status)
    except ValueError:
        return 0


# ===== Tài khoản =====
# Chỉ cho đăng ký bằng email nội bộ công ty
ALLOWED_EMAIL_DOMAINS = tuple(
    d.strip().lower()
    for d in os.environ.get("LUNCH_EMAIL_DOMAINS", "fpt.com").split(",")
    if d.strip()
)

MIN_PASSWORD_LENGTH = 8

# Thời hạn link đặt lại mật khẩu
RESET_TOKEN_TTL_MINUTES = 30

# Đăng nhập Google. Để trống thì nút Google tự ẩn đi, phần còn lại vẫn chạy.
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()


def email_domain_allowed(email: str) -> bool:
    if "@" not in email:
        return False
    return email.rsplit("@", 1)[1].lower() in ALLOWED_EMAIL_DOMAINS


def allowed_domains_label() -> str:
    return ", ".join("@" + d for d in ALLOWED_EMAIL_DOMAINS)


# ===== Upload ảnh =====
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
MAX_UPLOAD_BYTES = 4 * 1024 * 1024  # 4 MB, đủ cho ảnh món ăn và mã QR


def is_allowed_image(filename: str) -> bool:
    if "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS
