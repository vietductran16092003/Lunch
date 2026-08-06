"""Endpoint dành cho người đứng ra đặt (quản trị viên)."""

from flask import Blueprint, Response, jsonify, request

from ..core.security import SessionUser, require_admin


def build_admin_blueprint(services) -> Blueprint:
    bp = Blueprint("admin", __name__, url_prefix="/api/admin")

    # ===== Ảnh tải lên =====

    @bp.post("/uploads")
    @require_admin
    def upload_image():
        return jsonify(services.uploads.save(request.files.get("file"))), 201

    # ===== Nhà hàng =====

    @bp.post("/restaurants/preview")
    @require_admin
    def preview_restaurant():
        """Đọc thông tin từ đường dẫn GrabFood, chưa ghi database."""
        data = request.get_json(silent=True) or {}
        return jsonify(services.restaurants.preview_from_url(data.get("grab_url", "")))

    @bp.post("/restaurants")
    @require_admin
    def create_restaurant():
        data = request.get_json(silent=True) or {}
        return jsonify(services.restaurants.create(data)), 201

    @bp.put("/restaurants/<int:restaurant_id>")
    @require_admin
    def update_restaurant(restaurant_id):
        data = request.get_json(silent=True) or {}
        return jsonify(services.restaurants.update(restaurant_id, data))

    @bp.delete("/restaurants/<int:restaurant_id>")
    @require_admin
    def delete_restaurant(restaurant_id):
        services.restaurants.delete(restaurant_id)
        return jsonify({"status": "deleted"})

    # ===== Thực đơn =====

    @bp.post("/menu")
    @require_admin
    def create_menu_item():
        data = request.get_json(silent=True) or {}
        return jsonify(services.menu.create_item(data)), 201

    @bp.put("/menu/<int:item_id>")
    @require_admin
    def update_menu_item(item_id):
        data = request.get_json(silent=True) or {}
        return jsonify(services.menu.update_item(item_id, data))

    @bp.delete("/menu/<int:item_id>")
    @require_admin
    def delete_menu_item(item_id):
        return jsonify(services.menu.delete_item(item_id))

    # ===== Thông tin nhận tiền =====

    @bp.put("/payment-info")
    @require_admin
    def update_payment_info():
        data = request.get_json(silent=True) or {}
        services.users.update_payment_info(
            SessionUser.id(),
            (data.get("phone") or "").strip(),
            (data.get("qr_image_url") or "").strip(),
        )
        return jsonify({"status": "updated"})

    # ===== Giờ chốt đơn (4.1) =====

    @bp.put("/deadline")
    @require_admin
    def set_deadline():
        data = request.get_json(silent=True) or {}
        return jsonify(services.deadlines.configure(data))

    @bp.delete("/deadline/<date>")
    @require_admin
    def reset_deadline(date):
        """Bỏ giờ riêng của ngày, quay về giờ mặc định của hệ thống."""
        return jsonify(services.deadlines.reset(date))

    # ===== Bảng điều khiển =====

    @bp.get("/dashboard")
    @require_admin
    def dashboard():
        return jsonify(services.dashboard.build(request.args.get("date")))

    @bp.post("/orders/lock")
    @require_admin
    def lock_orders():
        """Chốt đơn và trả link Grab để frontend mở tab đặt hàng."""
        data = request.get_json(silent=True) or {}
        return jsonify(services.orders.lock_orders(data.get("date")))

    @bp.post("/orders/grab-placed")
    @require_admin
    def grab_placed():
        data = request.get_json(silent=True) or {}
        return jsonify(services.orders.mark_grab_placed(data.get("date")))

    @bp.post("/orders/<int:order_id>/confirm-payment")
    @require_admin
    def confirm_payment(order_id):
        return jsonify(services.orders.confirm_payment(order_id))

    @bp.get("/orders/export")
    @require_admin
    def export_orders():
        content, filename = services.reports.orders_csv(request.args.get("date"))
        return Response(
            content,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    return bp
