"""Endpoint thực đơn và nhà hàng (phần nhân viên xem được)."""

from flask import Blueprint, jsonify, request

from ..core.security import SessionUser, require_login


def build_menu_blueprint(services) -> Blueprint:
    bp = Blueprint("menu", __name__, url_prefix="/api")

    @bp.get("/menu")
    def get_menu():
        return jsonify(services.menu.get_menu(request.args.get("date")))

    @bp.get("/menu/dates")
    @require_login
    def menu_dates():
        """Ngày đã có thực đơn, để nhân viên chọn đặt hôm nay hay đặt trước hôm sau."""
        return jsonify(services.menu.available_dates(SessionUser.id()))

    @bp.get("/restaurants")
    @require_login
    def list_restaurants():
        return jsonify({"restaurants": services.restaurants.list_all()})

    return bp
