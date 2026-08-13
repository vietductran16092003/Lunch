"""Endpoint quản lý đặt hàng — mở cho mọi nhân viên đã đăng nhập, không còn
riêng admin. Ai đứng ra đặt cho một ngày thì tự nhận ngày đó (CollectorService);
ai cũng vào trang được và chọn NGÀY KHÁC để tự đứng ra đặt, chỉ riêng ngày đã
có người nhận thì người khác không sửa được thực đơn/chốt đơn/xác nhận thanh
toán cho đúng ngày đó (kiểm tra ở tầng service, route chỉ truyền actor).
Nhà hàng/danh mục món/xem bảng điều khiển là dữ liệu dùng chung, không khoá."""

from flask import Blueprint, Response, jsonify, request

from ..core.security import SessionUser, require_admin, require_login


def build_admin_blueprint(services) -> Blueprint:
    bp = Blueprint("admin", __name__, url_prefix="/api/admin")

    # ===== Ảnh tải lên (mã QR nhận tiền) =====

    @bp.post("/uploads")
    @require_login
    def upload_image():
        return jsonify(services.uploads.save(request.files.get("file"))), 201

    # ===== Nhà hàng — thêm mới là dữ liệu dùng chung, ai đăng nhập cũng thêm
    # được; sửa/xoá thì chỉ admin để tránh sửa nhầm dữ liệu người khác đã lưu =====

    @bp.post("/restaurants/preview")
    @require_login
    def preview_restaurant():
        """Đọc thông tin từ đường dẫn GrabFood, chưa ghi database."""
        data = request.get_json(silent=True) or {}
        return jsonify(services.restaurants.preview_from_url(data.get("grab_url", "")))

    @bp.post("/restaurants")
    @require_login
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

    # ===== Thực đơn — theo ngày, kiểm tra "người đặt" ở service =====

    @bp.post("/menu")
    @require_login
    def create_menu_item():
        """Thêm 1 món cho một ngày — người thêm đầu tiên của ngày đó tự thành người phụ trách."""
        data = request.get_json(silent=True) or {}
        return jsonify(
            services.menu.create_item(data, actor_id=SessionUser.id(), is_admin=SessionUser.is_admin())
        ), 201

    @bp.put("/menu/<int:item_id>")
    @require_login
    def update_menu_item(item_id):
        data = request.get_json(silent=True) or {}
        return jsonify(services.menu.update_item(
            item_id, data, actor_id=SessionUser.id(), is_admin=SessionUser.is_admin()
        ))

    @bp.delete("/menu/<int:item_id>")
    @require_login
    def delete_menu_item(item_id):
        return jsonify(services.menu.delete_item(
            item_id, actor_id=SessionUser.id(), is_admin=SessionUser.is_admin()
        ))

    # ===== Danh mục món gốc của nhà hàng (dùng lại nhiều ngày) =====

    @bp.get("/restaurants/<int:restaurant_id>/catalog")
    @require_login
    def list_catalog(restaurant_id):
        return jsonify(services.menu.list_catalog(restaurant_id))

    @bp.post("/restaurants/<int:restaurant_id>/catalog")
    @require_login
    def add_catalog_item(restaurant_id):
        data = request.get_json(silent=True) or {}
        return jsonify(services.menu.add_catalog_item(restaurant_id, data)), 201

    @bp.delete("/catalog/<int:catalog_id>")
    @require_login
    def delete_catalog_item(catalog_id):
        return jsonify(services.menu.delete_catalog_item(catalog_id))

    @bp.post("/menu/from-catalog")
    @require_login
    def apply_catalog_items():
        """Áp dụng hàng loạt món đã tick từ danh mục gốc vào thực đơn 1 ngày."""
        data = request.get_json(silent=True) or {}
        return jsonify(services.menu.apply_catalog_items(
            data.get("available_date"), data.get("restaurant_id"), data.get("catalog_ids") or [],
            actor_id=SessionUser.id(), is_admin=SessionUser.is_admin(),
        ))

    # ===== Thông tin nhận tiền — của chính người đang đăng nhập =====

    @bp.get("/payment-info")
    @require_login
    def my_payment_info():
        """Thông tin nhận tiền của chính người đang đăng nhập (không phải theo ngày)."""
        user = services.users.find_by_id(SessionUser.id())
        return jsonify(user.to_payment_info())

    @bp.put("/payment-info")
    @require_login
    def update_payment_info():
        # Chỉ đúng người đang đứng ra đặt đơn của VÒNG ĐANG MỞ mới sửa được —
        # kể cả admin cũng không, kể cả khi chưa ai nhận (phải tự đứng ra đặt
        # trước, bằng cách thêm món/đặt đơn, thì mới sửa được).
        if services.collectors:
            services.collectors.authorize_current_round_owner_only(
                SessionUser.id(), config=services.config
            )

        data = request.get_json(silent=True) or {}
        services.users.update_payment_info(
            SessionUser.id(),
            (data.get("phone") or "").strip(),
            (data.get("qr_image_url") or "").strip(),
        )
        return jsonify({"status": "updated"})

    # ===== Giờ chốt đơn (4.1) — vẫn của riêng admin, áp dụng toàn hệ thống =====

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

    # ===== Bảng điều khiển — xem được, chỉ chỉnh (chốt đơn/xác nhận) mới
    # kiểm tra "người đặt" ở service =====

    @bp.get("/dashboard")
    @require_login
    def dashboard():
        """Dữ liệu Bảng điều khiển của một ngày — ai cũng xem được, mở cho mọi người."""
        return jsonify(services.dashboard.build(request.args.get("date")))

    @bp.post("/orders/lock")
    @require_login
    def lock_orders():
        """Chốt đơn và trả link Grab để frontend mở tab đặt hàng."""
        data = request.get_json(silent=True) or {}
        return jsonify(services.orders.lock_orders(
            data.get("date"), actor_id=SessionUser.id(), is_admin=SessionUser.is_admin()
        ))

    @bp.post("/orders/grab-placed")
    @require_login
    def grab_placed():
        data = request.get_json(silent=True) or {}
        return jsonify(services.orders.mark_grab_placed(
            data.get("date"), actor_id=SessionUser.id(), is_admin=SessionUser.is_admin()
        ))

    @bp.post("/orders/<int:order_id>/confirm-payment")
    @require_login
    def confirm_payment(order_id):
        return jsonify(services.orders.confirm_payment(
            order_id, actor_id=SessionUser.id(), is_admin=SessionUser.is_admin()
        ))

    @bp.delete("/orders/day/<date>")
    @require_login
    def clear_day(date):
        """Gỡ bỏ hẳn một ngày đã lỡ dựng (thực đơn + đơn) — không áp dụng cho hôm nay."""
        return jsonify(services.orders.clear_date(
            date, actor_id=SessionUser.id(), is_admin=SessionUser.is_admin()
        ))

    @bp.get("/orders/export")
    @require_login
    def export_orders():
        content, filename = services.reports.orders_csv(request.args.get("date"))
        return Response(
            content,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    return bp
