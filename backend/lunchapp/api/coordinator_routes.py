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

    return bp
