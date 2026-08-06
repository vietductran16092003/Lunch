"""Xác thực: băm mật khẩu, đăng ký, đặt lại mật khẩu, đăng nhập Google.

Mật khẩu được băm bằng werkzeug (đi kèm Flask, không cần thư viện ngoài).
Các tài khoản cũ còn lưu mật khẩu dạng thô sẽ tự được băm lại ở lần đăng nhập
thành công đầu tiên — xem verify_and_upgrade_password().
"""

import json
import re
import secrets
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

import config

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_TIMEOUT_SECONDS = 6


class AuthError(ValueError):
    """Lỗi nghiệp vụ khi đăng ký / đăng nhập, thông điệp hiển thị được cho người dùng."""


# ===== Mật khẩu =====

def hash_password(password: str) -> str:
    return generate_password_hash(password)


def validate_password(password: str) -> None:
    if len(password or "") < config.MIN_PASSWORD_LENGTH:
        raise AuthError(f"Mật khẩu phải có ít nhất {config.MIN_PASSWORD_LENGTH} ký tự")


def validate_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise AuthError("Email không hợp lệ")
    if not config.email_domain_allowed(email):
        raise AuthError(
            f"Chỉ chấp nhận email nội bộ ({config.allowed_domains_label()})"
        )
    return email


def verify_and_upgrade_password(conn, user, password: str) -> bool:
    """Kiểm tra mật khẩu, đồng thời nâng cấp bản ghi cũ còn lưu dạng thô.

    Trả về True nếu đúng mật khẩu.
    """
    stored = user["password"] or ""

    # Bản ghi đã băm: werkzeug luôn ghi dạng "method$salt$hash"
    if stored.count("$") >= 2:
        return check_password_hash(stored, password)

    # Bản ghi cũ lưu thô — so trực tiếp rồi băm lại ngay để lần sau an toàn
    if secrets.compare_digest(stored, password):
        conn.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (hash_password(password), user["id"]),
        )
        conn.commit()
        return True

    return False


# ===== Đặt lại mật khẩu =====

def create_reset_token(conn, user_id: int) -> tuple[str, str]:
    """Sinh token đặt lại mật khẩu. Trả về (token, thời điểm hết hạn)."""
    token = secrets.token_urlsafe(32)
    expires = (datetime.now() + timedelta(minutes=config.RESET_TOKEN_TTL_MINUTES)).isoformat(
        timespec="seconds"
    )
    conn.execute(
        "UPDATE users SET reset_token = ?, reset_expires = ? WHERE id = ?",
        (token, expires, user_id),
    )
    conn.commit()
    return token, expires


def consume_reset_token(conn, token: str, new_password: str) -> None:
    """Đổi mật khẩu bằng token. Ném AuthError nếu token sai hoặc đã hết hạn."""
    if not token:
        raise AuthError("Thiếu mã đặt lại mật khẩu")

    user = conn.execute(
        "SELECT id, reset_expires FROM users WHERE reset_token = ?", (token,)
    ).fetchone()

    if user is None:
        raise AuthError("Link đặt lại mật khẩu không đúng hoặc đã được dùng")

    try:
        expired = datetime.fromisoformat(user["reset_expires"]) < datetime.now()
    except (TypeError, ValueError):
        expired = True

    if expired:
        raise AuthError("Link đặt lại mật khẩu đã hết hạn, vui lòng yêu cầu lại")

    validate_password(new_password)

    conn.execute(
        "UPDATE users SET password = ?, reset_token = NULL, reset_expires = NULL WHERE id = ?",
        (hash_password(new_password), user["id"]),
    )
    conn.commit()


# ===== Đăng nhập Google =====

def google_enabled() -> bool:
    return bool(config.GOOGLE_CLIENT_ID)


def verify_google_token(id_token: str) -> dict:
    """Xác minh id_token của Google và trả về thông tin tài khoản.

    Dùng endpoint tokeninfo của Google nên không cần thêm thư viện. Đủ an toàn ở
    quy mô nội bộ; nếu lưu lượng lớn thì nên đổi sang xác minh chữ ký cục bộ
    bằng google-auth.
    """
    if not google_enabled():
        raise AuthError("Quản trị viên chưa bật đăng nhập Google")

    if not id_token:
        raise AuthError("Thiếu mã xác thực từ Google")

    url = f"{GOOGLE_TOKENINFO_URL}?{urllib.parse.urlencode({'id_token': id_token})}"
    try:
        with urllib.request.urlopen(url, timeout=GOOGLE_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        raise AuthError("Không xác minh được tài khoản Google, vui lòng thử lại")

    if payload.get("aud") != config.GOOGLE_CLIENT_ID:
        raise AuthError("Mã xác thực Google không dành cho ứng dụng này")

    if payload.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise AuthError("Nguồn phát hành mã không hợp lệ")

    if payload.get("email_verified") not in ("true", True):
        raise AuthError("Email Google chưa được xác minh")

    email = (payload.get("email") or "").strip().lower()
    if not config.email_domain_allowed(email):
        raise AuthError(
            f"Chỉ chấp nhận tài khoản nội bộ ({config.allowed_domains_label()})"
        )

    return {
        "email": email,
        "name": payload.get("name") or email.split("@")[0],
        "google_sub": payload.get("sub"),
    }
