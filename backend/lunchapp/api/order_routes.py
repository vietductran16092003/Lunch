"""Endpoint đặt món của nhân viên."""

from flask import Blueprint, jsonify, request

from ..core.security import SessionUser, require_login


def build_order_blueprint(services) -> Blueprint:
    bp = Blueprint("orders", __name__, url_prefix="/api/orders")
    orders = services.orders

    @bp.post("")
    @require_login
    def create_order():
        data = request.get_json(silent=True) or {}
        result = orders.place_order(
            SessionUser.id(), data.get("items", []), data.get("order_date")
        )
        return jsonify(result), 201

    @bp.post("/reorder/<int:order_id>")
    @require_login
    def reorder(order_id):
        """Đặt lại nhanh từ một đơn cũ của chính mình (mã 3.3)."""
        data = request.get_json(silent=True) or {}
        result = orders.reorder_from(
            SessionUser.id(), order_id, data.get("order_date")
        )
        return jsonify(result), 201

    @bp.put("/<int:order_id>")
    @require_login
    def update_order(order_id):
        data = request.get_json(silent=True) or {}
        return jsonify(orders.update_order(order_id, SessionUser.id(), data.get("items", [])))

    @bp.delete("/<int:order_id>")
    @require_login
    def cancel_order(order_id):
        return jsonify(orders.cancel_order(order_id, SessionUser.id()))

    @bp.get("/my")
    @require_login
    def my_order():
        return jsonify(orders.my_order(SessionUser.id(), request.args.get("date")))

    @bp.post("/<int:order_id>/pay")
    @require_login
    def declare_payment(order_id):
        """Nhân viên báo đã chuyển khoản, chờ người đặt xác nhận."""
        return jsonify(orders.declare_payment(order_id, SessionUser.id()))

    @bp.get("/history")
    @require_login
    def history():
        return jsonify(orders.history(SessionUser.id()))

    @bp.get("/round-status")
    @require_login
    def round_status():
        """Ngày này đã có người nhận chưa, và vòng đặt còn dở dang hay không —
        frontend dùng để chặn người khác bấm vào "Đặt hàng chung" khi đang có
        đơn chưa hoàn tất."""
        return jsonify(orders.round_status(request.args.get("date")))

    return bp
