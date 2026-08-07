"""Endpoint quỹ chung: số dư, sổ quỹ, nạp/rút, công nợ (mã 5.3-5.6)."""

from flask import Blueprint, jsonify, request

from ..core.roles import Role
from ..core.security import SessionUser, require_role


def build_fund_blueprint(services) -> Blueprint:
    bp = Blueprint("fund", __name__, url_prefix="/api/fund")

    @bp.get("/balance")
    @require_role(Role.TREASURER, Role.ADMIN)
    def balance():
        return jsonify(services.fund.balance())

    @bp.get("/ledger")
    @require_role(Role.TREASURER, Role.ADMIN)
    def ledger():
        limit = request.args.get("limit", 100, type=int)
        return jsonify(services.fund.ledger(limit))

    @bp.post("/topup")
    @require_role(Role.TREASURER, Role.ADMIN)
    def topup():
        data = request.get_json(silent=True) or {}
        return jsonify(
            services.fund.topup(SessionUser.id(), data.get("amount"), data.get("note"))
        )

    @bp.post("/withdraw")
    @require_role(Role.TREASURER, Role.ADMIN)
    def withdraw():
        data = request.get_json(silent=True) or {}
        return jsonify(
            services.fund.withdraw(SessionUser.id(), data.get("amount"), data.get("note"))
        )

    @bp.get("/debts")
    @require_role(Role.TREASURER, Role.ADMIN)
    def debts():
        return jsonify(services.fund.debts(request.args.get("since")))

    # ===== Thanh toán đơn bằng quỹ (luồng 2) =====

    @bp.post("/pay-from-fund")
    @require_role(Role.TREASURER, Role.ADMIN)
    def pay_from_fund():
        data = request.get_json(silent=True) or {}
        return jsonify(
            services.fund.pay_orders_from_fund(data.get("date"), actor_id=SessionUser.id())
        )

    # ===== Góp quỹ hàng tháng (luồng 2) =====

    @bp.post("/dues")
    @require_role(Role.TREASURER, Role.ADMIN)
    def contribute_dues():
        data = request.get_json(silent=True) or {}
        return jsonify(services.fund.contribute_dues(
            data.get("user_id"), data.get("amount"), data.get("month"), data.get("note"),
        )), 201

    @bp.get("/dues")
    @require_role(Role.TREASURER, Role.ADMIN)
    def dues_overview():
        return jsonify(services.fund.dues_overview(request.args.get("month")))

    return bp
