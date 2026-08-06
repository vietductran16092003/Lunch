"""Endpoint phân quyền và lịch trực điều phối."""

from flask import Blueprint, jsonify, request

from ..core.roles import Role
from ..core.security import SessionUser, require_login, require_role


def build_role_blueprint(services) -> Blueprint:
    # Không đặt url_prefix vì nhóm endpoint này nằm ở hai nhánh khác nhau
    # (/api/admin/... và /api/coordinator/...).
    bp = Blueprint("roles", __name__, url_prefix="/api")

    # ===== Phân quyền người dùng =====

    @bp.get("/admin/users")
    @require_role(Role.ADMIN)
    def list_users():
        return jsonify({"users": services.auth.list_users()})

    @bp.put("/admin/users/<int:user_id>/roles")
    @require_role(Role.ADMIN)
    def update_user_roles(user_id):
        data = request.get_json(silent=True) or {}
        # Truyền actor_id để service biết ai đang thao tác mà chặn tự gỡ quyền
        return jsonify(
            services.auth.set_roles(user_id, data.get("roles"), actor_id=SessionUser.id())
        )

    # ===== Lịch trực điều phối =====

    @bp.get("/coordinator/schedule")
    @require_login
    def coordinator_schedule():
        """Mọi người đều xem được lịch — biết hôm nay ai đặt cơm là nhu cầu chung."""
        return jsonify(
            services.schedules.overview(request.args.get("from"), request.args.get("to"))
        )

    @bp.put("/admin/coordinator/schedule")
    @require_role(Role.ADMIN)
    def assign_coordinator():
        data = request.get_json(silent=True) or {}
        return jsonify(services.schedules.assign(data.get("date"), data.get("user_id")))

    @bp.delete("/admin/coordinator/schedule/<date>")
    @require_role(Role.ADMIN)
    def unassign_coordinator(date):
        return jsonify(services.schedules.unassign(date))

    return bp
