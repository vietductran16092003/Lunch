import os
import secrets
import uuid
from datetime import date, datetime
from functools import wraps

from flask import Flask, Response, jsonify, request, session, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

import auth
import config
import events
import grab_service
from database import get_connection, init_db

app = Flask(__name__)
app.secret_key = os.environ.get("LUNCH_APP_SECRET", "change-this-secret-key")
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_BYTES
CORS(app, supports_credentials=True)

os.makedirs(config.UPLOAD_DIR, exist_ok=True)


# ===== Tiện ích dùng chung =====

def _today():
    return date.today().isoformat()


def _now():
    return datetime.now().isoformat(timespec="seconds")


def require_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Chưa đăng nhập"}), 401
        return f(*args, **kwargs)

    return wrapper


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Chưa đăng nhập"}), 401
        if not session.get("is_admin"):
            return jsonify({"error": "Chỉ quản trị viên mới được thực hiện thao tác này"}), 403
        return f(*args, **kwargs)

    return wrapper


def _cutoff_error(action: str, target_date: str | None = None):
    if target_date and config.date_is_past(target_date):
        message = f"Ngày {target_date} đã qua, không thể {action}"
    else:
        message = f"Đã quá giờ chốt đơn ({config.order_cutoff_label()}), không thể {action}"
    return jsonify({"error": message, "cutoff": config.order_cutoff_label()}), 400


def _valid_date(value):
    """Nhận chuỗi YYYY-MM-DD, trả về None nếu sai định dạng."""
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError):
        return None


@app.errorhandler(413)
def handle_too_large(_error):
    limit_mb = config.MAX_UPLOAD_BYTES // (1024 * 1024)
    return jsonify({"error": f"Ảnh vượt quá {limit_mb} MB, vui lòng chọn ảnh nhỏ hơn"}), 413


@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "message": "Lunch App API đang chạy. Đây là backend, giao diện nằm ở địa chỉ frontend (thường là cổng 8080).",
        "health_check": "/api/health",
    })


# ===== Xác thực =====

def _start_session(user):
    session["user_id"] = user["id"]
    session["is_admin"] = bool(user["is_admin"])
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "is_admin": bool(user["is_admin"]),
    }


@app.route("/api/auth/options", methods=["GET"])
def auth_options():
    """Frontend hỏi xem có bật Google không và domain email nào được chấp nhận."""
    return jsonify({
        "google_enabled": auth.google_enabled(),
        "google_client_id": config.GOOGLE_CLIENT_ID,
        "allowed_domains": list(config.ALLOWED_EMAIL_DOMAINS),
        "allowed_domains_label": config.allowed_domains_label(),
        "min_password_length": config.MIN_PASSWORD_LENGTH,
    })


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Vui lòng nhập đầy đủ email và mật khẩu"}), 400

    conn = get_connection()
    user = conn.execute(
        "SELECT id, name, email, password, is_admin FROM users WHERE email = ?",
        (email,),
    ).fetchone()

    if user is None or not auth.verify_and_upgrade_password(conn, user, password):
        conn.close()
        return jsonify({"error": "Email hoặc mật khẩu không đúng"}), 401

    conn.close()
    return jsonify(_start_session(user))


@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    password = data.get("password") or ""

    if not name:
        return jsonify({"error": "Vui lòng nhập họ tên"}), 400

    try:
        email = auth.validate_email(data.get("email", ""))
        auth.validate_password(password)
    except auth.AuthError as err:
        return jsonify({"error": str(err)}), 400

    conn = get_connection()
    if conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
        conn.close()
        return jsonify({"error": "Email này đã được đăng ký, hãy đăng nhập"}), 409

    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (name, email, password, is_admin) VALUES (?, ?, ?, 0)",
        (name, email, auth.hash_password(password)),
    )
    conn.commit()
    user = conn.execute(
        "SELECT id, name, email, is_admin FROM users WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    conn.close()

    return jsonify(_start_session(user)), 201


@app.route("/api/auth/google", methods=["POST"])
def google_login():
    """Đăng nhập/đăng ký bằng Google. Nhận id_token từ Google Identity Services."""
    data = request.get_json(silent=True) or {}

    try:
        profile = auth.verify_google_token(data.get("credential", ""))
    except auth.AuthError as err:
        return jsonify({"error": str(err)}), 400

    conn = get_connection()
    user = conn.execute(
        "SELECT id, name, email, is_admin FROM users WHERE email = ?", (profile["email"],)
    ).fetchone()

    if user is None:
        # Lần đầu đăng nhập Google thì tạo luôn tài khoản, không cần mật khẩu
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (name, email, password, is_admin, google_sub) VALUES (?, ?, ?, 0, ?)",
            (profile["name"], profile["email"], auth.hash_password(secrets.token_urlsafe(32)),
             profile["google_sub"]),
        )
        conn.commit()
        user = conn.execute(
            "SELECT id, name, email, is_admin FROM users WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        created = True
    else:
        conn.execute(
            "UPDATE users SET google_sub = ? WHERE id = ?", (profile["google_sub"], user["id"])
        )
        conn.commit()
        created = False

    conn.close()
    payload = _start_session(user)
    payload["created"] = created
    return jsonify(payload)


@app.route("/api/password/forgot", methods=["POST"])
def password_forgot():
    """Tạo link đặt lại mật khẩu.

    Không tiết lộ email có tồn tại hay không, tránh dò tài khoản. Vì hệ thống
    chưa cấu hình SMTP, link được trả thẳng về màn hình cho môi trường nội bộ.
    """
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    generic = {
        "status": "sent",
        "message": "Nếu email tồn tại trong hệ thống, link đặt lại mật khẩu sẽ hiện bên dưới.",
    }

    if not email:
        return jsonify(generic)

    conn = get_connection()
    user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()

    if user is None:
        conn.close()
        return jsonify(generic)

    token, expires = auth.create_reset_token(conn, user["id"])
    conn.close()

    result = dict(generic)
    result["reset_token"] = token
    result["expires_at"] = expires
    result["ttl_minutes"] = config.RESET_TOKEN_TTL_MINUTES
    return jsonify(result)


@app.route("/api/password/reset", methods=["POST"])
def password_reset():
    data = request.get_json(silent=True) or {}
    conn = get_connection()
    try:
        auth.consume_reset_token(conn, data.get("token", ""), data.get("password", ""))
    except auth.AuthError as err:
        conn.close()
        return jsonify({"error": str(err)}), 400
    conn.close()
    return jsonify({"status": "reset"})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "logged_out"})


@app.route("/api/me", methods=["GET"])
@require_login
def me():
    conn = get_connection()
    user = conn.execute(
        "SELECT id, name, email, is_admin FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()
    conn.close()

    if user is None:
        session.clear()
        return jsonify({"error": "Người dùng không tồn tại"}), 401

    return jsonify({
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "is_admin": bool(user["is_admin"]),
    })


# ===== Cấu hình cho frontend =====

@app.route("/api/config", methods=["GET"])
def client_config():
    """Frontend đọc giờ chốt đơn và nhãn trạng thái từ đây, không cần hardcode lại."""
    return jsonify({
        "cutoff": config.order_cutoff_label(),
        "cutoff_passed": config.order_cutoff_passed(),
        "steps": [
            {"key": key, "label": config.STATUS_LABELS[key]} for key in config.ORDER_STEPS
        ],
    })


# ===== Thông báo thời gian thực =====

@app.route("/api/stream", methods=["GET"])
@require_login
def stream():
    q = events.subscribe()

    def generate():
        try:
            yield from events.stream(q)
        finally:
            events.unsubscribe(q)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ===== Ảnh tải lên =====

@app.route("/api/uploads/<path:filename>", methods=["GET"])
def serve_upload(filename):
    return send_from_directory(config.UPLOAD_DIR, filename)


@app.route("/api/admin/uploads", methods=["POST"])
@require_admin
def upload_image():
    """Nhận một file ảnh, trả về đường dẫn dùng được ngay trong thẻ <img>."""
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify({"error": "Vui lòng chọn một file ảnh"}), 400

    if not config.is_allowed_image(file.filename):
        allowed = ", ".join(sorted(config.ALLOWED_IMAGE_EXTENSIONS))
        return jsonify({"error": f"Chỉ chấp nhận ảnh định dạng: {allowed}"}), 400

    extension = file.filename.rsplit(".", 1)[1].lower()
    safe_stem = secure_filename(file.filename.rsplit(".", 1)[0]) or "anh"
    stored_name = f"{safe_stem[:40]}-{uuid.uuid4().hex[:8]}.{extension}"
    file.save(os.path.join(config.UPLOAD_DIR, stored_name))

    return jsonify({"url": f"/api/uploads/{stored_name}", "filename": stored_name}), 201


# ===== Nhà hàng (GrabFood) =====

@app.route("/api/restaurants", methods=["GET"])
@require_login
def list_restaurants():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, grab_url, address, rating, image_url FROM restaurants ORDER BY name"
    ).fetchall()
    conn.close()
    return jsonify({"restaurants": [dict(r) for r in rows]})


@app.route("/api/admin/restaurants/preview", methods=["POST"])
@require_admin
def preview_restaurant():
    """Đọc thông tin nhà hàng từ đường dẫn GrabFood để quản trị viên xem trước.

    Chưa ghi vào database — quản trị viên xác nhận rồi mới lưu.
    """
    data = request.get_json(silent=True) or {}
    try:
        info = grab_service.parse_restaurant_url(data.get("grab_url", ""))
    except grab_service.GrabUrlError as err:
        return jsonify({"error": str(err)}), 400

    return jsonify({
        "restaurant": info,
        "fetched": info["source"] == "fetch",
        "hint": None if info["source"] == "fetch"
        else "Đã đọc tên từ đường dẫn — vui lòng kiểm tra và sửa lại cho đúng trước khi lưu.",
    })


@app.route("/api/admin/restaurants", methods=["POST"])
@require_admin
def create_restaurant():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    grab_url = (data.get("grab_url") or "").strip()

    if not name:
        return jsonify({"error": "Vui lòng nhập tên nhà hàng"}), 400
    if grab_url and not grab_service.is_grab_url(grab_url):
        return jsonify({"error": "Đường dẫn phải thuộc food.grab.com"}), 400

    rating = data.get("rating")
    try:
        rating = float(rating) if rating not in (None, "") else None
    except (TypeError, ValueError):
        rating = None

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO restaurants (name, grab_url, external_id, address, rating, image_url) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            name,
            grab_url or None,
            (data.get("external_id") or "").strip() or None,
            (data.get("address") or "").strip() or None,
            rating,
            (data.get("image_url") or "").strip() or None,
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    events.publish("restaurant_added", {"id": new_id, "name": name})
    return jsonify({"id": new_id, "name": name}), 201


@app.route("/api/admin/restaurants/<int:restaurant_id>", methods=["DELETE"])
@require_admin
def delete_restaurant(restaurant_id):
    conn = get_connection()
    in_use = conn.execute(
        "SELECT COUNT(*) AS total FROM menu_items WHERE restaurant_id = ?", (restaurant_id,)
    ).fetchone()["total"]
    if in_use:
        conn.close()
        return jsonify({
            "error": f"Nhà hàng đang có {in_use} món trong thực đơn, hãy xóa món trước"
        }), 400

    conn.execute("DELETE FROM restaurants WHERE id = ?", (restaurant_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})


# ===== Thực đơn =====

@app.route("/api/menu/dates", methods=["GET"])
@require_login
def menu_dates():
    """Những ngày đã có thực đơn, tính từ hôm nay trở đi.

    Nhân viên dùng danh sách này để chọn đặt cho hôm nay hay đặt trước cho hôm
    sau, khi quản trị viên đã lên thực đơn sớm.
    """
    today = _today()

    conn = get_connection()
    rows = conn.execute(
        """
        SELECT menu_items.available_date AS date,
               COUNT(*) AS item_count
        FROM menu_items
        WHERE menu_items.available_date >= ?
        GROUP BY menu_items.available_date
        ORDER BY menu_items.available_date
        """,
        (today,),
    ).fetchall()

    ordered_dates = {
        r["order_date"]
        for r in conn.execute(
            "SELECT DISTINCT order_date FROM orders WHERE user_id = ? AND order_date >= ?",
            (session["user_id"], today),
        ).fetchall()
    }
    conn.close()

    dates = []
    for r in rows:
        dates.append({
            "date": r["date"],
            "item_count": r["item_count"],
            "is_today": r["date"] == today,
            "closed": config.cutoff_passed_for(r["date"]),
            "has_order": r["date"] in ordered_dates,
        })

    # Mặc định mở ngày còn đặt được gần nhất, nếu hôm nay đã chốt thì nhảy sang hôm sau
    default_date = next((d["date"] for d in dates if not d["closed"]), today)

    return jsonify({
        "today": today,
        "dates": dates,
        "default_date": default_date,
        "cutoff": config.order_cutoff_label(),
    })


@app.route("/api/menu", methods=["GET"])
def get_menu():
    target_date = _valid_date(request.args.get("date")) or _today()

    conn = get_connection()
    items = conn.execute(
        """
        SELECT menu_items.id, menu_items.name, menu_items.description,
               menu_items.price, menu_items.available_date, menu_items.image_url,
               menu_items.restaurant_id,
               restaurants.name AS restaurant_name,
               restaurants.rating AS restaurant_rating,
               restaurants.grab_url AS restaurant_grab_url
        FROM menu_items
        LEFT JOIN restaurants ON menu_items.restaurant_id = restaurants.id
        WHERE menu_items.available_date = ?
        ORDER BY restaurants.name, menu_items.name
        """,
        (target_date,),
    ).fetchall()
    conn.close()

    return jsonify({
        "date": target_date,
        "cutoff": config.order_cutoff_label(),
        # Giờ chốt chỉ áp cho hôm nay; ngày sau vẫn đặt trước được
        "cutoff_passed": config.cutoff_passed_for(target_date),
        "is_today": target_date == _today(),
        "items": [dict(item) for item in items],
    })


@app.route("/api/admin/menu", methods=["POST"])
@require_admin
def admin_create_menu_item():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    price = data.get("price")
    available_date = data.get("available_date")
    restaurant_id = data.get("restaurant_id")

    if not name or price is None or not available_date:
        return jsonify({"error": "Vui lòng nhập đủ tên món, giá, ngày áp dụng"}), 400

    # Yêu cầu nghiệp vụ: phải chọn nhà hàng trước khi thêm món
    if not restaurant_id:
        return jsonify({"error": "Vui lòng chọn nhà hàng trước khi thêm món"}), 400

    conn = get_connection()
    restaurant = conn.execute(
        "SELECT id FROM restaurants WHERE id = ?", (restaurant_id,)
    ).fetchone()
    if restaurant is None:
        conn.close()
        return jsonify({"error": "Nhà hàng không tồn tại"}), 400

    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO menu_items (name, description, price, available_date, restaurant_id, image_url) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            name,
            data.get("description") or "",
            price,
            available_date,
            restaurant_id,
            (data.get("image_url") or "").strip() or None,
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    events.publish("menu_updated", {"id": new_id, "name": name, "date": available_date})
    return jsonify({"id": new_id}), 201


@app.route("/api/admin/menu/<int:item_id>", methods=["PUT"])
@require_admin
def admin_update_menu_item(item_id):
    data = request.get_json(silent=True) or {}
    conn = get_connection()
    existing = conn.execute("SELECT id FROM menu_items WHERE id = ?", (item_id,)).fetchone()
    if existing is None:
        conn.close()
        return jsonify({"error": "Không tìm thấy món ăn"}), 404

    conn.execute(
        """UPDATE menu_items
           SET name = ?, description = ?, price = ?, available_date = ?,
               restaurant_id = ?, image_url = ?
           WHERE id = ?""",
        (
            data.get("name"), data.get("description"), data.get("price"),
            data.get("available_date"), data.get("restaurant_id"),
            (data.get("image_url") or "").strip() or None, item_id,
        ),
    )
    conn.commit()
    conn.close()

    events.publish("menu_updated", {"id": item_id})
    return jsonify({"status": "updated"})


@app.route("/api/admin/menu/<int:item_id>", methods=["DELETE"])
@require_admin
def admin_delete_menu_item(item_id):
    conn = get_connection()
    conn.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

    events.publish("menu_updated", {"id": item_id, "deleted": True})
    return jsonify({"status": "deleted"})


# ===== Thông tin thanh toán của quản trị viên =====

@app.route("/api/payment-info", methods=["GET"])
@require_login
def payment_info():
    """Thông tin liên hệ và QR thanh toán của quản trị viên (người đứng ra đặt đồ)."""
    conn = get_connection()
    admin_user = conn.execute(
        "SELECT name, phone, qr_image_url FROM users WHERE is_admin = 1 ORDER BY id LIMIT 1"
    ).fetchone()
    conn.close()

    if admin_user is None:
        return jsonify({"name": None, "phone": None, "qr_image_url": None})

    return jsonify({
        "name": admin_user["name"],
        "phone": admin_user["phone"],
        "qr_image_url": admin_user["qr_image_url"],
    })


@app.route("/api/admin/payment-info", methods=["PUT"])
@require_admin
def admin_update_payment_info():
    data = request.get_json(silent=True) or {}
    phone = (data.get("phone") or "").strip()
    qr_image_url = (data.get("qr_image_url") or "").strip()

    conn = get_connection()
    conn.execute(
        "UPDATE users SET phone = ?, qr_image_url = ? WHERE id = ?",
        (phone or None, qr_image_url or None, session["user_id"]),
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "updated"})


# ===== Đơn hàng của nhân viên =====

def _load_order_items(conn, order_id):
    rows = conn.execute(
        """
        SELECT order_items.menu_item_id, order_items.quantity,
               menu_items.name, menu_items.price, menu_items.image_url
        FROM order_items
        JOIN menu_items ON order_items.menu_item_id = menu_items.id
        WHERE order_items.order_id = ?
        """,
        (order_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _row_get(row, key):
    return row[key] if key in row.keys() else None


def _serialize_order(conn, order):
    items = _load_order_items(conn, order["id"])
    paid_at = _row_get(order, "paid_at")
    confirmed_at = _row_get(order, "payment_confirmed_at")
    return {
        "id": order["id"],
        "order_date": _row_get(order, "order_date"),
        "status": order["status"],
        "status_label": config.STATUS_LABELS.get(order["status"], order["status"]),
        "step_index": config.status_index(order["status"]),
        "payment_method": order["payment_method"],
        "paid_at": paid_at,
        "payment_confirmed_at": confirmed_at,
        # Nhân viên đã báo chuyển khoản nhưng quản trị viên chưa xác nhận nhận tiền
        "awaiting_confirmation": bool(paid_at) and not confirmed_at,
        "items": items,
        "total_cost": sum(i["price"] * i["quantity"] for i in items),
    }


@app.route("/api/orders", methods=["POST"])
@require_login
def create_order():
    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    # Hệ thống chỉ còn hình thức chuyển khoản cho người đứng ra đặt
    payment_method = "transfer"

    # Cho phép đặt trước cho ngày sau nếu quản trị viên đã lên thực đơn sớm
    target_date = _valid_date(data.get("order_date")) or _today()

    if config.cutoff_passed_for(target_date):
        return _cutoff_error("đặt món", target_date)

    if not items:
        return jsonify({"error": "Vui lòng chọn ít nhất một món"}), 400

    user_id = session["user_id"]

    conn = get_connection()
    cursor = conn.cursor()

    # Món phải thuộc đúng thực đơn của ngày được đặt, tránh đặt nhầm ngày
    requested_ids = [i.get("menu_item_id") for i in items if i.get("quantity", 0) > 0]
    if not requested_ids:
        conn.close()
        return jsonify({"error": "Vui lòng chọn ít nhất một món"}), 400

    placeholders = ",".join("?" * len(requested_ids))
    valid_ids = {
        r["id"]
        for r in cursor.execute(
            f"SELECT id FROM menu_items WHERE available_date = ? AND id IN ({placeholders})",
            (target_date, *requested_ids),
        ).fetchall()
    }
    if set(requested_ids) - valid_ids:
        conn.close()
        return jsonify({"error": f"Có món không thuộc thực đơn ngày {target_date}"}), 400

    # Một người một đơn mỗi ngày: đặt lại thì ghi đè đơn đang chờ thay vì tạo trùng
    existing = cursor.execute(
        "SELECT id, status FROM orders WHERE user_id = ? AND order_date = ? ORDER BY id DESC LIMIT 1",
        (user_id, target_date),
    ).fetchone()

    if existing and existing["status"] != config.STATUS_PENDING:
        conn.close()
        return jsonify({"error": f"Đơn ngày {target_date} đã được chốt, không thể đặt thêm"}), 400

    if existing:
        order_id = existing["id"]
        cursor.execute(
            "UPDATE orders SET payment_method = ? WHERE id = ?", (payment_method, order_id)
        )
        cursor.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
    else:
        cursor.execute(
            "INSERT INTO orders (user_id, order_date, status, payment_method) VALUES (?, ?, ?, ?)",
            (user_id, target_date, config.STATUS_PENDING, payment_method),
        )
        order_id = cursor.lastrowid

    for item in items:
        quantity = item.get("quantity", 0)
        if quantity and quantity > 0:
            cursor.execute(
                "INSERT INTO order_items (order_id, menu_item_id, quantity) VALUES (?, ?, ?)",
                (order_id, item.get("menu_item_id"), quantity),
            )

    conn.commit()
    user = conn.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    events.publish("order_placed", {
        "order_id": order_id,
        "employee_name": user["name"] if user else "Một nhân viên",
        "item_count": len(items),
        "updated": bool(existing),
        "order_date": target_date,
        "is_advance": target_date != _today(),
    })

    return jsonify({
        "id": order_id, "status": config.STATUS_PENDING, "order_date": target_date
    }), 201


@app.route("/api/orders/<int:order_id>", methods=["PUT"])
@require_login
def update_order(order_id):
    conn = get_connection()
    order = conn.execute(
        "SELECT id, user_id, status, order_date FROM orders WHERE id = ?", (order_id,)
    ).fetchone()

    if order is None or order["user_id"] != session["user_id"]:
        conn.close()
        return jsonify({"error": "Không tìm thấy đơn hàng"}), 404

    # Giờ chốt tính theo ngày của chính đơn đó, không phải theo hôm nay
    if config.cutoff_passed_for(order["order_date"]):
        conn.close()
        return _cutoff_error("sửa đơn", order["order_date"])

    if order["status"] != config.STATUS_PENDING:
        conn.close()
        return jsonify({"error": "Đơn hàng đã được chốt, không thể sửa"}), 400

    data = request.get_json(silent=True) or {}

    cursor = conn.cursor()
    cursor.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
    for item in data.get("items", []):
        quantity = item.get("quantity", 0)
        if quantity and quantity > 0:
            cursor.execute(
                "INSERT INTO order_items (order_id, menu_item_id, quantity) VALUES (?, ?, ?)",
                (order_id, item.get("menu_item_id"), quantity),
            )
    conn.commit()
    conn.close()

    events.publish("order_updated", {"order_id": order_id})
    return jsonify({"id": order_id, "status": "updated"})


@app.route("/api/orders/<int:order_id>", methods=["DELETE"])
@require_login
def delete_order(order_id):
    conn = get_connection()
    order = conn.execute(
        "SELECT id, user_id, status, order_date FROM orders WHERE id = ?", (order_id,)
    ).fetchone()

    if order is None or order["user_id"] != session["user_id"]:
        conn.close()
        return jsonify({"error": "Không tìm thấy đơn hàng"}), 404

    if config.cutoff_passed_for(order["order_date"]):
        conn.close()
        return _cutoff_error("hủy đơn", order["order_date"])

    if order["status"] != config.STATUS_PENDING:
        conn.close()
        return jsonify({"error": "Đơn hàng đã được chốt, không thể hủy"}), 400

    cursor = conn.cursor()
    cursor.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
    cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()

    events.publish("order_cancelled", {"order_id": order_id})
    return jsonify({"status": "deleted"})


@app.route("/api/orders/my", methods=["GET"])
@require_login
def my_order_today():
    target_date = _valid_date(request.args.get("date")) or _today()

    conn = get_connection()
    order = conn.execute(
        "SELECT id, order_date, status, payment_method, paid_at, payment_confirmed_at "
        "FROM orders WHERE user_id = ? AND order_date = ? ORDER BY id DESC LIMIT 1",
        (session["user_id"], target_date),
    ).fetchone()

    payload = _serialize_order(conn, order) if order is not None else None
    conn.close()

    return jsonify({
        "order": payload,
        "date": target_date,
        "is_today": target_date == _today(),
        "cutoff": config.order_cutoff_label(),
        "cutoff_passed": config.cutoff_passed_for(target_date),
    })


_ORDER_SELECT = (
    "SELECT id, user_id, order_date, status, payment_method, paid_at, payment_confirmed_at "
    "FROM orders WHERE id = ?"
)


@app.route("/api/orders/<int:order_id>/pay", methods=["POST"])
@require_login
def declare_payment(order_id):
    """Nhân viên báo đã chuyển khoản.

    Chưa tính là xong: đơn chỉ chuyển sang "Hoàn tất" khi quản trị viên bấm xác
    nhận đã nhận được tiền.
    """
    conn = get_connection()
    order = conn.execute(_ORDER_SELECT, (order_id,)).fetchone()

    if order is None or order["user_id"] != session["user_id"]:
        conn.close()
        return jsonify({"error": "Không tìm thấy đơn hàng"}), 404

    if order["status"] == config.STATUS_PENDING:
        conn.close()
        return jsonify({"error": "Đơn chưa được chốt, chưa cần thanh toán"}), 400

    if order["paid_at"]:
        payload = _serialize_order(conn, order)
        conn.close()
        return jsonify({"status": "already_declared", "order": payload})

    paid_at = _now()
    conn.execute("UPDATE orders SET paid_at = ? WHERE id = ?", (paid_at, order_id))
    conn.commit()

    refreshed = conn.execute(_ORDER_SELECT, (order_id,)).fetchone()
    payload = _serialize_order(conn, refreshed)
    user = conn.execute("SELECT name FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    conn.close()

    events.publish("payment_declared", {
        "order_id": order_id,
        "employee_name": user["name"] if user else "Một nhân viên",
        "amount": payload["total_cost"],
        "paid_at": paid_at,
    })

    return jsonify({"status": "awaiting_confirmation", "order": payload})


@app.route("/api/admin/orders/<int:order_id>/confirm-payment", methods=["POST"])
@require_admin
def admin_confirm_payment(order_id):
    """Quản trị viên xác nhận đã nhận được tiền của một nhân viên."""
    conn = get_connection()
    order = conn.execute(_ORDER_SELECT, (order_id,)).fetchone()

    if order is None:
        conn.close()
        return jsonify({"error": "Không tìm thấy đơn hàng"}), 404

    if order["status"] == config.STATUS_PENDING:
        conn.close()
        return jsonify({"error": "Đơn chưa được chốt"}), 400

    if order["payment_confirmed_at"]:
        payload = _serialize_order(conn, order)
        conn.close()
        return jsonify({"status": "already_confirmed", "order": payload})

    now = _now()
    # Nhân viên đưa tiền trực tiếp mà chưa bấm báo thì ghi luôn mốc thanh toán
    paid_at = order["paid_at"] or now
    conn.execute(
        "UPDATE orders SET status = ?, paid_at = ?, payment_confirmed_at = ? WHERE id = ?",
        (config.STATUS_COMPLETED, paid_at, now, order_id),
    )
    conn.commit()

    refreshed = conn.execute(_ORDER_SELECT, (order_id,)).fetchone()
    payload = _serialize_order(conn, refreshed)
    employee = conn.execute(
        "SELECT name FROM users WHERE id = ?", (order["user_id"],)
    ).fetchone()
    conn.close()

    events.publish("payment_confirmed", {
        "order_id": order_id,
        "user_id": order["user_id"],
        "employee_name": employee["name"] if employee else "Nhân viên",
        "amount": payload["total_cost"],
        "confirmed_at": now,
    })

    return jsonify({"status": "confirmed", "order": payload})


@app.route("/api/orders/history", methods=["GET"])
@require_login
def order_history():
    conn = get_connection()
    orders = conn.execute(
        "SELECT id, order_date, status, payment_method, paid_at, payment_confirmed_at "
        "FROM orders WHERE user_id = ? ORDER BY order_date DESC, id DESC",
        (session["user_id"],),
    ).fetchall()

    admin_user = conn.execute(
        "SELECT name FROM users WHERE is_admin = 1 ORDER BY id LIMIT 1"
    ).fetchone()

    history = []
    for order in orders:
        items = conn.execute(
            """
            SELECT menu_items.name, menu_items.price, order_items.quantity,
                   restaurants.name AS restaurant_name
            FROM order_items
            JOIN menu_items ON order_items.menu_item_id = menu_items.id
            LEFT JOIN restaurants ON menu_items.restaurant_id = restaurants.id
            WHERE order_items.order_id = ?
            ORDER BY menu_items.name
            """,
            (order["id"],),
        ).fetchall()

        # Kèm sẵn thành tiền từng dòng để giao diện không phải tự nhân lại
        item_list = []
        for i in items:
            item_list.append({
                "name": i["name"],
                "price": i["price"],
                "quantity": i["quantity"],
                "line_cost": i["price"] * i["quantity"],
                "restaurant_name": i["restaurant_name"],
            })

        paid_at = order["paid_at"]
        confirmed_at = order["payment_confirmed_at"]

        if confirmed_at:
            payment_state, payment_label = "confirmed", "Người đặt đã xác nhận nhận tiền"
        elif paid_at:
            payment_state, payment_label = "awaiting", "Đã chuyển, chờ người đặt xác nhận"
        elif order["status"] == config.STATUS_PENDING:
            payment_state, payment_label = "not_due", "Chưa đến lúc thanh toán"
        else:
            payment_state, payment_label = "unpaid", "Chưa thanh toán"

        history.append({
            "id": order["id"],
            "order_date": order["order_date"],
            "status": order["status"],
            "status_label": config.STATUS_LABELS.get(order["status"], order["status"]),
            "payment_method": order["payment_method"],
            "paid_at": paid_at,
            "payment_confirmed_at": confirmed_at,
            "payment_state": payment_state,
            "payment_label": payment_label,
            "collector_name": admin_user["name"] if admin_user else None,
            "items": item_list,
            "total_cost": sum(i["line_cost"] for i in item_list),
        })
    conn.close()

    return jsonify({"history": history})


# ===== Bảng điều khiển quản trị (gộp tổng hợp + chi tiết nhân viên) =====

@app.route("/api/admin/dashboard", methods=["GET"])
@require_admin
def admin_dashboard():
    """Một endpoint duy nhất thay cho /summary và /by-employee cũ.

    Trả về đồng thời: tổng hợp theo món (để đặt trên Grab), chi tiết theo nhân
    viên (để tính tiền) và trạng thái chung của ngày.
    """
    target_date = _valid_date(request.args.get("date")) or _today()

    conn = get_connection()

    # Những ngày có thực đơn hoặc có đơn, để quản trị viên chuyển qua lại và
    # theo dõi cả đơn đặt trước cho hôm sau
    known_dates = [
        r["date"]
        for r in conn.execute(
            """
            SELECT DISTINCT available_date AS date FROM menu_items WHERE available_date >= ?
            UNION
            SELECT DISTINCT order_date AS date FROM orders WHERE order_date >= ?
            ORDER BY date
            """,
            (_today(), _today()),
        ).fetchall()
    ]

    by_item = conn.execute(
        """
        SELECT menu_items.id AS menu_item_id,
               menu_items.name AS item_name,
               menu_items.price AS price,
               restaurants.name AS restaurant_name,
               restaurants.grab_url AS restaurant_grab_url,
               SUM(order_items.quantity) AS total_quantity
        FROM order_items
        JOIN orders ON order_items.order_id = orders.id
        JOIN menu_items ON order_items.menu_item_id = menu_items.id
        LEFT JOIN restaurants ON menu_items.restaurant_id = restaurants.id
        WHERE orders.order_date = ?
        GROUP BY menu_items.id
        ORDER BY restaurants.name, menu_items.name
        """,
        (target_date,),
    ).fetchall()

    rows = conn.execute(
        """
        SELECT users.id AS employee_id,
               users.name AS employee_name,
               users.email AS employee_email,
               menu_items.name AS item_name,
               menu_items.price AS price,
               order_items.quantity AS quantity,
               orders.id AS order_id,
               orders.status AS status,
               orders.payment_method AS payment_method,
               orders.paid_at AS paid_at,
               orders.payment_confirmed_at AS payment_confirmed_at
        FROM order_items
        JOIN orders ON order_items.order_id = orders.id
        JOIN users ON orders.user_id = users.id
        JOIN menu_items ON order_items.menu_item_id = menu_items.id
        WHERE orders.order_date = ?
        ORDER BY users.name, menu_items.name
        """,
        (target_date,),
    ).fetchall()

    status_counts = conn.execute(
        "SELECT status, COUNT(*) AS total FROM orders WHERE order_date = ? GROUP BY status",
        (target_date,),
    ).fetchall()

    restaurants = conn.execute(
        """
        SELECT DISTINCT restaurants.id, restaurants.name, restaurants.grab_url
        FROM menu_items
        JOIN restaurants ON menu_items.restaurant_id = restaurants.id
        WHERE menu_items.available_date = ?
        """,
        (target_date,),
    ).fetchall()
    conn.close()

    employees = {}
    for r in rows:
        key = r["employee_email"]
        if key not in employees:
            revealed = r["status"] in (
                config.STATUS_CLOSED, config.STATUS_ORDERED, config.STATUS_COMPLETED
            )
            employees[key] = {
                "order_id": r["order_id"],
                "employee_name": r["employee_name"],
                "employee_email": r["employee_email"],
                "status": r["status"],
                "status_label": config.STATUS_LABELS.get(r["status"], r["status"]),
                # Phương thức thanh toán chỉ lộ ra sau khi đơn đã chốt — trước đó
                # nhân viên vẫn có thể đổi ý nên chưa cần biết
                "payment_method": r["payment_method"] if revealed else None,
                "paid": bool(r["paid_at"]),
                "paid_at": r["paid_at"],
                "confirmed": bool(r["payment_confirmed_at"]),
                "payment_confirmed_at": r["payment_confirmed_at"],
                # Nhân viên báo đã chuyển, quản trị viên cần bấm xác nhận
                "awaiting_confirmation": bool(r["paid_at"]) and not r["payment_confirmed_at"],
                "items": [],
                "total_cost": 0,
            }
        line_cost = r["price"] * r["quantity"]
        employees[key]["items"].append({
            "item_name": r["item_name"],
            "price": r["price"],
            "quantity": r["quantity"],
            "line_cost": line_cost,
        })
        employees[key]["total_cost"] += line_cost

    employee_list = list(employees.values())
    counts = {row["status"]: row["total"] for row in status_counts}
    summary = [dict(r) for r in by_item]

    return jsonify({
        "date": target_date,
        "today": _today(),
        "is_today": target_date == _today(),
        "available_dates": known_dates,
        "cutoff": config.order_cutoff_label(),
        "cutoff_passed": config.cutoff_passed_for(target_date),
        "summary": summary,
        "employees": employee_list,
        "restaurants": [dict(r) for r in restaurants],
        "totals": {
            "grand_total": sum(e["total_cost"] for e in employee_list),
            "employee_count": len(employee_list),
            "item_count": sum(s["total_quantity"] for s in summary),
            "paid_count": sum(1 for e in employee_list if e["confirmed"]),
            "awaiting_count": sum(1 for e in employee_list if e["awaiting_confirmation"]),
            "collected_amount": sum(e["total_cost"] for e in employee_list if e["confirmed"]),
        },
        "status_counts": counts,
        "locked": bool(
            counts.get(config.STATUS_CLOSED)
            or counts.get(config.STATUS_ORDERED)
            or counts.get(config.STATUS_COMPLETED)
        ),
    })


@app.route("/api/admin/orders/lock", methods=["POST"])
@require_admin
def admin_lock_orders():
    """Hành động chính duy nhất: chốt đơn và mở luôn Grab để đặt.

    Gộp hai nút "Chốt đơn" và "Đánh dấu đã đặt" cũ thành một bước.
    Trả về đường dẫn Grab để frontend mở tab mới ngay.
    """
    data = request.get_json(silent=True) or {}
    target_date = _valid_date(data.get("date")) or _today()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE orders SET status = ?, locked_at = ? WHERE order_date = ? AND status = ?",
        (config.STATUS_CLOSED, _now(), target_date, config.STATUS_PENDING),
    )
    locked_count = cursor.rowcount
    conn.commit()

    restaurants = conn.execute(
        """
        SELECT DISTINCT restaurants.id, restaurants.name, restaurants.grab_url
        FROM order_items
        JOIN orders ON order_items.order_id = orders.id
        JOIN menu_items ON order_items.menu_item_id = menu_items.id
        JOIN restaurants ON menu_items.restaurant_id = restaurants.id
        WHERE orders.order_date = ? AND restaurants.grab_url IS NOT NULL
        """,
        (target_date,),
    ).fetchall()
    conn.close()

    grab_links = [dict(r) for r in restaurants]
    events.publish("orders_locked", {"date": target_date, "locked_count": locked_count})

    return jsonify({
        "status": config.STATUS_CLOSED,
        "date": target_date,
        "locked_count": locked_count,
        "grab_links": grab_links,
    })


@app.route("/api/admin/orders/grab-placed", methods=["POST"])
@require_admin
def admin_grab_placed():
    """Xác nhận đã mở/đặt xong trên Grab — chuyển đơn sang trạng thái chờ thanh toán.

    Frontend gọi ngay sau khi mở tab Grab, nên quản trị viên không phải bấm thêm nút.
    """
    data = request.get_json(silent=True) or {}
    target_date = _valid_date(data.get("date")) or _today()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE orders SET status = ? WHERE order_date = ? AND status = ?",
        (config.STATUS_ORDERED, target_date, config.STATUS_CLOSED),
    )
    updated = cursor.rowcount
    conn.commit()
    conn.close()

    events.publish("orders_ordered", {"date": target_date, "count": updated})
    return jsonify({"status": config.STATUS_ORDERED, "date": target_date, "count": updated})


@app.route("/api/admin/orders/export", methods=["GET"])
@require_admin
def admin_export_orders():
    """Xuất CSV chi tiết theo từng nhân viên, có sẵn thành tiền để không phải tính tay."""
    import csv
    import io

    from flask import Response as FlaskResponse

    target_date = _valid_date(request.args.get("date")) or _today()

    conn = get_connection()
    rows = conn.execute(
        """
        SELECT users.name AS employee_name,
               restaurants.name AS restaurant_name,
               menu_items.name AS item_name,
               menu_items.price AS price,
               order_items.quantity AS quantity,
               orders.status AS status,
               orders.payment_method AS payment_method,
               orders.paid_at AS paid_at,
               orders.payment_confirmed_at AS payment_confirmed_at
        FROM order_items
        JOIN orders ON order_items.order_id = orders.id
        JOIN users ON orders.user_id = users.id
        JOIN menu_items ON order_items.menu_item_id = menu_items.id
        LEFT JOIN restaurants ON menu_items.restaurant_id = restaurants.id
        WHERE orders.order_date = ?
        ORDER BY users.name, menu_items.name
        """,
        (target_date,),
    ).fetchall()
    conn.close()

    output = io.StringIO()
    output.write("﻿")  # BOM để Excel mở đúng tiếng Việt
    writer = csv.writer(output)
    writer.writerow([
        "Nhân viên", "Nhà hàng", "Món ăn", "Đơn giá", "Số lượng",
        "Thành tiền", "Nhân viên báo đã chuyển", "Người đặt đã xác nhận",
    ])
    for r in rows:
        writer.writerow([
            r["employee_name"], r["restaurant_name"] or "", r["item_name"],
            r["price"], r["quantity"], r["price"] * r["quantity"],
            "Rồi" if r["paid_at"] else "Chưa",
            "Rồi" if r["payment_confirmed_at"] else "Chưa",
        ])

    return FlaskResponse(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=don-hang-{target_date}.csv"
        },
    )


@app.route("/api/health", methods=["GET"])
def health():
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return jsonify({
        "status": "ok",
        "database": db_status,
        "cutoff": config.order_cutoff_label(),
    })


if __name__ == "__main__":
    init_db()
    # threaded=True là bắt buộc: mỗi kết nối /api/stream giữ một luồng riêng
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
