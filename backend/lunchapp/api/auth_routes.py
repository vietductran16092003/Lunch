"""Endpoint xác thực."""

from flask import Blueprint, current_app, jsonify, request

from ..core.errors import UnauthorizedError
from ..core.security import SessionUser, require_login


def build_auth_blueprint(services) -> Blueprint:
    bp = Blueprint("auth", __name__, url_prefix="/api")
    auth = services.auth

    def _session_payload(user) -> dict:
        SessionUser.login(user.id, user.is_admin)
        return user.to_dict()

    @bp.get("/auth/options")
    def auth_options():
        """Frontend hỏi có bật Google không và domain email nào được chấp nhận."""
        return jsonify(auth.auth_options())

    @bp.post("/login")
    def login():
        data = request.get_json(silent=True) or {}
        user = auth.login(data.get("email", ""), data.get("password", ""))
        return jsonify(_session_payload(user))

    @bp.post("/register")
    def register():
        data = request.get_json(silent=True) or {}
        user = auth.register(
            data.get("name", ""), data.get("email", ""), data.get("password", "")
        )
        return jsonify(_session_payload(user)), 201

    @bp.post("/auth/google")
    def google_login():
        """Đăng nhập/đăng ký bằng Google. Nhận id_token từ Google Identity Services."""
        data = request.get_json(silent=True) or {}
        user, created = auth.login_with_google(data.get("credential", ""))
        payload = _session_payload(user)
        payload["created"] = created
        return jsonify(payload)

    @bp.post("/password/forgot")
    def password_forgot():
        """Tạo link đặt lại mật khẩu.

        Không tiết lộ email có tồn tại hay không, tránh dò tài khoản. Vì chưa cấu
        hình SMTP, link được trả thẳng về màn hình cho môi trường nội bộ.
        """
        data = request.get_json(silent=True) or {}
        result = {
            "status": "sent",
            "message": "Nếu email tồn tại trong hệ thống, link đặt lại mật khẩu sẽ hiện bên dưới.",
        }
        issued = auth.create_reset_token(data.get("email", ""))
        if issued:
            result.update(issued)
        return jsonify(result)

    @bp.post("/password/reset")
    def password_reset():
        data = request.get_json(silent=True) or {}
        auth.reset_password(data.get("token", ""), data.get("password", ""))
        return jsonify({"status": "reset"})

    @bp.post("/logout")
    def logout():
        SessionUser.logout()
        return jsonify({"status": "logged_out"})

    @bp.get("/me")
    @require_login
    def me():
        user = services.users.find_by_id(SessionUser.id())
        if user is None:
            SessionUser.logout()
            raise UnauthorizedError("Người dùng không tồn tại")
        return jsonify(user.to_dict())

    @bp.get("/payment-info")
    @require_login
    def payment_info():
        """Liên hệ và QR của người đứng ra đặt, để nhân viên chuyển khoản."""
        admin = services.users.find_primary_admin()
        if admin is None:
            return jsonify({"name": None, "phone": None, "qr_image_url": None})
        return jsonify(admin.to_payment_info())

    return bp
