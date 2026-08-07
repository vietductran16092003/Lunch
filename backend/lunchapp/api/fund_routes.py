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

    return bp
