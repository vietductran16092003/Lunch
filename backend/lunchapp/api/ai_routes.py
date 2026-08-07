"""Endpoint cho các tính năng AI/gợi ý (Phase 3)."""

from flask import Blueprint, jsonify, request

from ..core.roles import Role
from ..core.security import SessionUser, require_login, require_role


def build_ai_blueprint(services) -> Blueprint:
    bp = Blueprint("ai", __name__, url_prefix="/api/ai")
    ai = services.ai

    @bp.get("/suggestions")
    @require_login
    def suggestions():
        return jsonify(ai.suggest_items(SessionUser.id(), request.args.get("date")))

    @bp.post("/extract-menu")
    @require_role(Role.ADMIN)
    def extract_menu():
        data = request.get_json(silent=True) or {}
        return jsonify(ai.extract_menu_text(
            data.get("text", ""), data.get("restaurant_id"), data.get("available_date")
        ))

    @bp.post("/extract-menu/save")
    @require_role(Role.ADMIN)
    def save_extracted_menu():
        data = request.get_json(silent=True) or {}
        return jsonify(ai.bulk_create_items(
            data.get("items", []), data.get("restaurant_id"), data.get("available_date")
        )), 201

    @bp.get("/summary")
    @require_role(Role.COORDINATOR, Role.TREASURER, Role.ADMIN)
    def summary():
        return jsonify(ai.summarize_day(request.args.get("date")))

    @bp.get("/report")
    @require_role(Role.COORDINATOR, Role.TREASURER, Role.ADMIN)
    def report():
        return jsonify(ai.range_report(
            request.args.get("start"), request.args.get("end")
        ))

    @bp.get("/reminders")
    @require_role(Role.COORDINATOR, Role.ADMIN)
    def reminders():
        return jsonify(ai.pending_reminders(request.args.get("date")))

    @bp.post("/chat")
    @require_login
    def chat():
        data = request.get_json(silent=True) or {}
        return jsonify(ai.chat_reply(SessionUser.id(), data.get("message", "")))

    return bp
