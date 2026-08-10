"""Endpoint phân quyền người dùng."""

from flask import Blueprint, jsonify, request

from ..core.roles import Role
from ..core.security import SessionUser, require_role


def build_role_blueprint(services) -> Blueprint:
    bp = Blueprint("roles", __name__, url_prefix="/api/admin")

    @bp.get("/users")
    @require_role(Role.ADMIN)
    def list_users():
        return jsonify({"users": services.auth.list_users()})

    @bp.put("/users/<int:user_id>/roles")
    @require_role(Role.ADMIN)
    def update_user_roles(user_id):
        data = request.get_json(silent=True) or {}
        # Truyền actor_id để service biết ai đang thao tác mà chặn tự gỡ quyền
        return jsonify(
            services.auth.set_roles(user_id, data.get("roles"), actor_id=SessionUser.id())
        )

    @bp.delete("/users/<int:user_id>")
    @require_role(Role.ADMIN)
    def delete_user(user_id):
        return jsonify(services.auth.delete_user(user_id, actor_id=SessionUser.id()))

    return bp
