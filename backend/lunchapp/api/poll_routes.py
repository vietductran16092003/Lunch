"""Endpoint bình chọn quán ăn (Phase 4)."""

from flask import Blueprint, jsonify, request

from ..core.roles import Role
from ..core.security import SessionUser, require_login, require_role


def build_poll_blueprint(services) -> Blueprint:
    bp = Blueprint("polls", __name__, url_prefix="/api/polls")
    polls = services.polls

    @bp.get("/current")
    @require_login
    def current():
        return jsonify(polls.current(request.args.get("date"), SessionUser.id()))

    @bp.post("")
    @require_role(Role.COORDINATOR, Role.ADMIN)
    def create():
        data = request.get_json(silent=True) or {}
        return jsonify(polls.create_poll(
            data.get("question"), data.get("options", []),
            data.get("poll_date"), SessionUser.id(),
        )), 201

    @bp.post("/<int:poll_id>/vote")
    @require_login
    def vote(poll_id):
        data = request.get_json(silent=True) or {}
        return jsonify(polls.vote(poll_id, data.get("option_id"), SessionUser.id()))

    @bp.post("/<int:poll_id>/close")
    @require_role(Role.COORDINATOR, Role.ADMIN)
    def close(poll_id):
        return jsonify(polls.close(poll_id))

    return bp
