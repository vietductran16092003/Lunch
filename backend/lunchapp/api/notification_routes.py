"""Endpoint trung tâm thông báo."""

from flask import Blueprint, jsonify, request

from ..core.security import SessionUser, require_login


def build_notification_blueprint(services) -> Blueprint:
    bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")

    @bp.get("")
    @require_login
    def list_notifications():
        limit = request.args.get("limit", 30, type=int)
        return jsonify(
            services.notifications.list_for_user(SessionUser.id(), SessionUser.roles(), limit)
        )

    @bp.post("/<int:notification_id>/read")
    @require_login
    def mark_read(notification_id):
        return jsonify(services.notifications.mark_read(notification_id, SessionUser.id()))

    @bp.post("/read-all")
    @require_login
    def mark_all_read():
        return jsonify(
            services.notifications.mark_all_read(SessionUser.id(), SessionUser.roles())
        )

    return bp
