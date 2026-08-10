"""Endpoint gộp đơn/chia ship/thông báo — nay chỉ admin dùng, sau khi bỏ vai
trò điều phối viên riêng (gộp thẳng vào trang Đặt hàng của admin)."""

from flask import Blueprint, jsonify, request

from ..core.roles import Role
from ..core.security import SessionUser, require_role


def build_coordinator_blueprint(services) -> Blueprint:
    bp = Blueprint("coordinator", __name__, url_prefix="/api/coordinator")

    # ===== Gộp đơn theo quán (mã 4.2) =====

    @bp.get("/grouped")
    @require_role(Role.ADMIN)
    def grouped():
        """Tổng số lượng từng món theo từng quán của một ngày, kèm ghi chú (mã 3.5)
        để tiện copy tay vào Grab."""
        return jsonify(services.orders.grouped_by_restaurant(request.args.get("date")))

    # ===== Chia phí ship (mã 4.3) =====

    @bp.post("/split-shipping")
    @require_role(Role.ADMIN)
    def split_shipping():
        data = request.get_json(silent=True) or {}
        return jsonify(
            services.fund.split_shipping(
                data.get("date"), data.get("total_fee"), actor_id=SessionUser.id()
            )
        )

    # ===== Danh bạ nhân viên (dùng cho form góp quỹ) =====

    @bp.get("/employees")
    @require_role(Role.TREASURER, Role.ADMIN)
    def employees():
        return jsonify({"users": services.auth.list_users()})

    # ===== Thông báo chung (Phase 4) =====

    @bp.post("/broadcast")
    @require_role(Role.ADMIN)
    def broadcast():
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        if not message:
            return jsonify({"error": "Vui lòng nhập nội dung thông báo"}), 400

        sender = services.users.find_by_id(SessionUser.id())
        services.events.publish("announcement", {
            "message": message, "from": sender.name if sender else "Quản trị",
        })
        return jsonify({"status": "sent"})

    return bp
