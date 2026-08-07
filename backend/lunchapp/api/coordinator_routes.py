"""Endpoint dành cho người điều phối (coordinator).

File này có thể được nhiều mã song song nối thêm route (xem mã 4.2 gộp theo
quán) — giữ cấu trúc `build_coordinator_blueprint(services)` đơn giản để dễ nối.
"""

from flask import Blueprint, jsonify, request

from ..core.roles import Role
from ..core.security import SessionUser, require_role


def build_coordinator_blueprint(services) -> Blueprint:
    bp = Blueprint("coordinator", __name__, url_prefix="/api/coordinator")

    # ===== Gộp đơn theo quán (mã 4.2) =====

    @bp.get("/grouped")
    @require_role(Role.COORDINATOR, Role.ADMIN)
    def grouped():
        """Tổng số lượng từng món theo từng quán của một ngày, kèm ghi chú (mã 3.5)
        để coordinator tiện copy tay vào Grab."""
        return jsonify(services.orders.grouped_by_restaurant(request.args.get("date")))

    # ===== Chia phí ship (mã 4.3) =====

    @bp.post("/split-shipping")
    @require_role(Role.COORDINATOR, Role.ADMIN)
    def split_shipping():
        data = request.get_json(silent=True) or {}
        return jsonify(
            services.fund.split_shipping(
                data.get("date"), data.get("total_fee"), actor_id=SessionUser.id()
            )
        )

    # ===== Đặt hộ nhân viên (Phase 4) =====

    @bp.get("/employees")
    @require_role(Role.COORDINATOR, Role.ADMIN)
    def employees():
        """Danh bạ rút gọn để chọn người đặt hộ."""
        return jsonify({"users": services.auth.list_users()})

    @bp.post("/orders-for/<int:user_id>")
    @require_role(Role.COORDINATOR, Role.ADMIN)
    def place_order_for(user_id):
        data = request.get_json(silent=True) or {}
        result = services.orders.place_order(
            user_id, data.get("items", []), data.get("order_date")
        )
        return jsonify(result), 201

    # ===== Thông báo chung (Phase 4) =====

    @bp.post("/broadcast")
    @require_role(Role.COORDINATOR, Role.ADMIN)
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
