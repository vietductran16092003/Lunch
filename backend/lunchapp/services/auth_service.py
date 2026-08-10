"""Nghiệp vụ xác thực: đăng nhập, đăng ký, đặt lại mật khẩu, đăng nhập Google."""

import json
import re
import secrets
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from ..config import Config
from ..core.errors import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from ..core.roles import Role

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class GoogleTokenVerifier:
    """Xác minh id_token của Google.

    Dùng endpoint tokeninfo nên không cần thêm thư viện. Đủ an toàn ở quy mô nội
    bộ; lưu lượng lớn thì nên đổi sang xác minh chữ ký cục bộ bằng google-auth.
    """

    TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
    VALID_ISSUERS = ("accounts.google.com", "https://accounts.google.com")

    def __init__(self, config=Config):
        self.config = config

    def verify(self, id_token: str) -> dict:
        if not self.config.google_enabled():
            raise ValidationError("Quản trị viên chưa bật đăng nhập Google")
        if not id_token:
            raise ValidationError("Thiếu mã xác thực từ Google")

        payload = self._fetch(id_token)

        if payload.get("aud") != self.config.GOOGLE_CLIENT_ID:
            raise ValidationError("Mã xác thực Google không dành cho ứng dụng này")
        if payload.get("iss") not in self.VALID_ISSUERS:
            raise ValidationError("Nguồn phát hành mã không hợp lệ")
        if payload.get("email_verified") not in ("true", True):
            raise ValidationError("Email Google chưa được xác minh")

        email = (payload.get("email") or "").strip().lower()
        if not self.config.email_domain_allowed(email):
            raise ValidationError(
                f"Chỉ chấp nhận tài khoản nội bộ ({self.config.allowed_domains_label()})"
            )

        return {
            "email": email,
            "name": payload.get("name") or email.split("@")[0],
            "google_sub": payload.get("sub"),
        }

    def _fetch(self, id_token: str) -> dict:
        url = f"{self.TOKENINFO_URL}?{urllib.parse.urlencode({'id_token': id_token})}"
        try:
            with urllib.request.urlopen(url, timeout=self.config.GRAB_FETCH_TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            raise ValidationError("Không xác minh được tài khoản Google, vui lòng thử lại")


class AuthService:
    """Đăng nhập, đăng ký và quản lý mật khẩu."""

    def __init__(self, user_repository, config=Config, google_verifier=None):
        self.users = user_repository
        self.config = config
        self.google = google_verifier or GoogleTokenVerifier(config)

    # ===== Mật khẩu =====

    @staticmethod
    def hash_password(password: str) -> str:
        return generate_password_hash(password)

    def validate_password(self, password: str):
        if len(password or "") < self.config.MIN_PASSWORD_LENGTH:
            raise ValidationError(
                f"Mật khẩu phải có ít nhất {self.config.MIN_PASSWORD_LENGTH} ký tự"
            )

    def validate_email(self, email: str) -> str:
        email = (email or "").strip().lower()
        if not EMAIL_PATTERN.match(email):
            raise ValidationError("Email không hợp lệ")
        if not self.config.email_domain_allowed(email):
            raise ValidationError(
                f"Chỉ chấp nhận email nội bộ ({self.config.allowed_domains_label()})"
            )
        return email

    # ===== Đăng nhập =====

    def login(self, email: str, password: str):
        email = (email or "").strip().lower()
        if not email or not password:
            raise ValidationError("Vui lòng nhập đầy đủ email và mật khẩu")

        user = self.users.find_by_email(email)
        if user is None or not self._verify_and_upgrade(user, password):
            raise UnauthorizedError("Email hoặc mật khẩu không đúng")
        return user

    def _verify_and_upgrade(self, user, password: str) -> bool:
        """Kiểm tra mật khẩu, đồng thời băm lại bản ghi cũ còn lưu dạng thô."""
        stored = user.password or ""

        if user.has_hashed_password():
            return check_password_hash(stored, password)

        if secrets.compare_digest(stored, password):
            self.users.update_password(user.id, self.hash_password(password))
            return True
        return False

    # ===== Đăng ký =====

    def register(self, name: str, email: str, password: str):
        name = (name or "").strip()
        if not name:
            raise ValidationError("Vui lòng nhập họ tên")

        email = self.validate_email(email)
        self.validate_password(password)

        if self.users.email_exists(email):
            raise ConflictError("Email này đã được đăng ký, hãy đăng nhập")

        return self.users.create(name, email, self.hash_password(password))

    # ===== Google =====

    def login_with_google(self, credential: str) -> tuple:
        """Trả về (user, đã_tạo_mới)."""
        profile = self.google.verify(credential)

        user = self.users.find_by_email(profile["email"])
        if user is None:
            # Lần đầu đăng nhập Google thì tạo luôn tài khoản, không cần mật khẩu
            user = self.users.create(
                name=profile["name"],
                email=profile["email"],
                password_hash=self.hash_password(secrets.token_urlsafe(32)),
                google_sub=profile["google_sub"],
            )
            return user, True

        self.users.update_google_sub(user.id, profile["google_sub"])
        return user, False

    # ===== Đặt lại mật khẩu =====

    def create_reset_token(self, email: str) -> dict | None:
        """Trả về None nếu email không tồn tại — người gọi không được tiết lộ điều đó."""
        email = (email or "").strip().lower()
        if not email:
            return None

        user = self.users.find_by_email(email)
        if user is None:
            return None

        token = secrets.token_urlsafe(32)
        expires = (
            datetime.now() + timedelta(minutes=self.config.RESET_TOKEN_TTL_MINUTES)
        ).isoformat(timespec="seconds")
        self.users.set_reset_token(user.id, token, expires)

        return {
            "reset_token": token,
            "expires_at": expires,
            "ttl_minutes": self.config.RESET_TOKEN_TTL_MINUTES,
        }

    def reset_password(self, token: str, new_password: str):
        if not token:
            raise ValidationError("Thiếu mã đặt lại mật khẩu")

        user = self.users.find_by_reset_token(token)
        if user is None:
            raise ValidationError("Link đặt lại mật khẩu không đúng hoặc đã được dùng")

        try:
            expired = datetime.fromisoformat(user.reset_expires) < datetime.now()
        except (TypeError, ValueError):
            expired = True

        if expired:
            raise ValidationError("Link đặt lại mật khẩu đã hết hạn, vui lòng yêu cầu lại")

        self.validate_password(new_password)
        self.users.clear_reset_token_and_set_password(
            user.id, self.hash_password(new_password)
        )

    # ===== Phân quyền =====

    def list_users(self) -> list:
        """Danh bạ rút gọn cho màn hình phân quyền."""
        return [user.to_directory_entry() for user in self.users.list_all()]

    def role_catalog(self) -> list:
        """Danh mục vai trò kèm nhãn tiếng Việt, để frontend khỏi hard-code."""
        return [{"value": role, "label": Role.label(role)} for role in Role.ALL]

    def set_roles(self, user_id, roles, actor_id=None) -> dict:
        """Ghi đè vai trò của một người.

        Hai lá chắn ở đây tồn tại vì cùng một lý do: hệ thống không được rơi vào
        trạng thái không còn ai vào được trang quản trị.
        """
        user = self.users.find_by_id(user_id)
        if user is None:
            raise NotFoundError("Không tìm thấy người dùng")

        if not isinstance(roles, (list, tuple, set)):
            raise ValidationError("Danh sách vai trò không hợp lệ")

        invalid = Role.invalid_items(roles)
        if invalid:
            raise ValidationError(f"Vai trò không hợp lệ: {', '.join(map(str, invalid))}")

        wanted = Role.sort(Role.clean_many(roles))
        if not wanted:
            raise ValidationError("Mỗi người phải giữ ít nhất một vai trò")

        losing_admin = user.has_role(Role.ADMIN) and Role.ADMIN not in wanted

        if losing_admin:
            # Tự gỡ quyền của chính mình là cách nhanh nhất để tự khoá cửa
            if actor_id is not None and int(actor_id) == int(user.id):
                raise ConflictError("Bạn không thể tự gỡ vai trò quản trị viên của chính mình")
            if self.users.count_with_role(Role.ADMIN) <= 1:
                raise ConflictError("Hệ thống phải còn ít nhất một quản trị viên")

        self.users.replace_roles(user.id, wanted)
        return self.users.find_by_id(user.id).to_directory_entry()

    def delete_user(self, user_id, actor_id=None) -> dict:
        """Xoá hẳn một tài khoản khỏi hệ thống.

        Chặn xoá chính mình (tự khoá cửa), xoá quản trị viên cuối cùng, và xoá
        người đã có lịch sử đặt món (mất dấu vết đối soát thu chi) — những
        trường hợp này nên đổi vai trò thay vì xoá tài khoản.
        """
        user = self.users.find_by_id(user_id)
        if user is None:
            raise NotFoundError("Không tìm thấy người dùng")

        if actor_id is not None and int(actor_id) == int(user.id):
            raise ConflictError("Bạn không thể tự xoá chính mình")

        if user.has_role(Role.ADMIN) and self.users.count_with_role(Role.ADMIN) <= 1:
            raise ConflictError("Hệ thống phải còn ít nhất một quản trị viên")

        if self.users.has_orders(user.id):
            raise ConflictError(
                "Người này đã có lịch sử đặt món, không thể xoá — đổi vai trò thay vì xoá"
            )

        self.users.delete(user.id)
        return {"status": "deleted"}

    # ===== Cấu hình cho frontend =====

    def auth_options(self) -> dict:
        return {
            "google_enabled": self.config.google_enabled(),
            "google_client_id": self.config.GOOGLE_CLIENT_ID,
            "allowed_domains": list(self.config.ALLOWED_EMAIL_DOMAINS),
            "allowed_domains_label": self.config.allowed_domains_label(),
            "min_password_length": self.config.MIN_PASSWORD_LENGTH,
        }
