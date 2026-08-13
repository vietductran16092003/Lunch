"""Người đứng ra đặt của một ngày không cố định ở admin — ai thêm món đầu tiên
cho một ngày thì tự nhận ngày đó, và thông tin nhận tiền hiển thị cho nhân
viên là của chính người đó."""

from datetime import date, timedelta

from lunchapp import Config

from .conftest import login, login_employee

FUTURE_DATE = (date.today() + timedelta(days=5)).isoformat()


def test_payment_info_follows_the_days_owner(client, container):
    restaurant_id = container.restaurant_repo.list_all()[0].id
    current_round_date = Config.current_order_date()

    login_employee(client)
    client.post("/api/admin/menu", json={
        "name": "Cơm nhân viên", "price": 25000,
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_id,
    })
    # Sửa thông tin nhận tiền chỉ được khi đúng chủ của VÒNG ĐANG MỞ — tự
    # nhận thêm ngày đó để có quyền sửa, không ảnh hưởng gì tới việc test GET
    # theo ngày tương lai ở dưới.
    client.post("/api/admin/menu", json={
        "name": "Cơm vòng hiện tại", "price": 20000,
        "available_date": current_round_date, "restaurant_id": restaurant_id,
    })
    client.put("/api/admin/payment-info", json={"phone": "0900000111", "qr_image_url": ""})
    client.post("/api/logout")

    login(client)
    resp = client.get(f"/api/payment-info?date={FUTURE_DATE}")
    assert resp.status_code == 200
    assert resp.get_json()["phone"] == "0900000111"
    assert resp.get_json()["name"] == "Nhân viên demo"


def test_payment_info_falls_back_to_admin_when_unclaimed(client, container):
    resp = client.get("/api/payment-info")
    assert resp.status_code == 401

    login(client)
    resp = client.get(f"/api/payment-info?date={FUTURE_DATE}")
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Admin"


def test_round_status_open_while_orders_not_all_completed(client, container):
    restaurant_id = container.restaurant_repo.list_all()[0].id

    login_employee(client)
    resp = client.get(f"/api/orders/round-status?date={FUTURE_DATE}")
    assert resp.get_json() == {"date": FUTURE_DATE, "owner": None, "is_open": False}

    item_id = client.post("/api/admin/menu", json={
        "name": "Cơm dở dang", "price": 25000,
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_id,
    }).get_json()["id"]

    # Chỉ có thực đơn, chưa ai đặt gì thì chưa có gì phải hoàn tất
    resp = client.get(f"/api/orders/round-status?date={FUTURE_DATE}")
    data = resp.get_json()
    assert data["owner"]["name"] == "Nhân viên demo"
    assert data["is_open"] is False

    client.post("/api/orders", json={
        "items": [{"menu_item_id": item_id, "quantity": 1}], "order_date": FUTURE_DATE,
    })
    resp = client.get(f"/api/orders/round-status?date={FUTURE_DATE}")
    assert resp.get_json()["is_open"] is True


def test_round_status_closes_once_orders_completed(client, container):
    restaurant_id = container.restaurant_repo.list_all()[0].id

    login_employee(client)
    item_id = client.post("/api/admin/menu", json={
        "name": "Cơm hoàn tất", "price": 25000,
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_id,
    }).get_json()["id"]
    order_id = client.post("/api/orders", json={
        "items": [{"menu_item_id": item_id, "quantity": 1}], "order_date": FUTURE_DATE,
    }).get_json()["id"]
    client.post("/api/admin/orders/lock", json={"date": FUTURE_DATE})
    client.post(f"/api/admin/orders/{order_id}/confirm-payment")

    resp = client.get(f"/api/orders/round-status?date={FUTURE_DATE}")
    assert resp.get_json()["is_open"] is False


def test_shared_resources_stay_open_regardless_of_todays_owner(client, container):
    """Nhà hàng/danh mục món là dữ liệu dùng chung — ai đã đăng nhập cũng
    THÊM được, kể cả khi hôm nay đã có người khác phụ trách. Người đó vẫn tự
    do chọn NGÀY KHÁC để đứng ra đặt của riêng mình. Riêng SỬA/XOÁ nhà hàng
    thì chỉ admin (tránh sửa nhầm dữ liệu người khác đã lưu)."""
    restaurant_id = container.restaurant_repo.list_all()[0].id
    today = date.today().isoformat()

    login_employee(client)
    client.post("/api/admin/menu", json={
        "name": "Cơm hôm nay", "price": 25000,
        "available_date": today, "restaurant_id": restaurant_id,
    })
    client.post("/api/logout")

    # Đăng ký nhân viên B mới để không trùng với người đang phụ trách hôm nay
    client.post("/api/register", json={
        "name": "Nhan vien B", "email": "nhanvienb@fpt.com", "password": "password123",
    })

    resp = client.post("/api/admin/restaurants", json={"name": "Quán khác"})
    assert resp.status_code == 201

    resp = client.post(f"/api/admin/restaurants/{restaurant_id}/catalog", json={
        "name": "Món mới", "price": 10000,
    })
    assert resp.status_code == 201

    # Nhân viên B không sửa/xoá được nhà hàng — chỉ admin mới được
    resp = client.put(f"/api/admin/restaurants/{restaurant_id}", json={"name": "Đổi tên"})
    assert resp.status_code == 403
    resp = client.delete(f"/api/admin/restaurants/{restaurant_id}")
    assert resp.status_code == 403

    # ...nhưng vẫn đứng ra đặt được cho một ngày KHÁC (chưa ai nhận)
    resp = client.post("/api/admin/menu", json={
        "name": "Món B tự đặt", "price": 20000,
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_id,
    })
    assert resp.status_code == 201

    # Xem bảng điều khiển của NGÀY HÔM NAY (do người khác phụ trách) vẫn được
    resp = client.get(f"/api/admin/dashboard?date={today}")
    assert resp.status_code == 200

    # Nhưng KHÔNG chốt được đơn của ngày hôm nay — đó là ngày người khác phụ trách
    resp = client.post("/api/admin/orders/lock", json={"date": today})
    assert resp.status_code == 403


def test_cannot_edit_payment_info_when_today_unclaimed(client, container):
    """Chưa tự đứng ra đặt hôm nay thì chưa sửa được thông tin nhận tiền —
    phải thêm món/đặt đơn hôm nay để tự nhận trước."""
    login_employee(client)
    resp = client.put("/api/admin/payment-info", json={"phone": "0911222333", "qr_image_url": ""})
    assert resp.status_code == 403


def test_can_edit_own_payment_info_when_owner_of_today(client, container):
    """Tự đứng ra đặt của vòng đang mở (thêm món đầu tiên) rồi thì sửa được
    thông tin nhận tiền của chính mình."""
    restaurant_id = container.restaurant_repo.list_all()[0].id
    current_round_date = Config.current_order_date()

    login_employee(client)
    client.post("/api/admin/menu", json={
        "name": "Cơm vòng hiện tại", "price": 25000,
        "available_date": current_round_date, "restaurant_id": restaurant_id,
    })
    resp = client.put("/api/admin/payment-info", json={"phone": "0911222333", "qr_image_url": ""})
    assert resp.status_code == 200

    resp = client.get("/api/admin/payment-info")
    assert resp.status_code == 200
    assert resp.get_json()["phone"] == "0911222333"
    assert resp.get_json()["name"] == "Nhân viên demo"


def test_payment_info_locked_for_non_owner_of_today(client, container):
    """Đã có người phụ trách vòng đang mở thì tài khoản khác — kể cả admin —
    không sửa được thông tin nhận tiền của chính mình qua trang Đặt hàng nữa,
    phải chờ vòng sau hoặc tự đứng ra đặt ngày khác."""
    restaurant_id = container.restaurant_repo.list_all()[0].id
    current_round_date = Config.current_order_date()

    login_employee(client)
    client.post("/api/admin/menu", json={
        "name": "Cơm vòng hiện tại", "price": 25000,
        "available_date": current_round_date, "restaurant_id": restaurant_id,
    })
    client.post("/api/logout")

    login(client)
    resp = client.put("/api/admin/payment-info", json={"phone": "0900000000", "qr_image_url": ""})
    assert resp.status_code == 403

    resp = client.post("/api/coordinator/broadcast", json={"message": "Xin chào"})
    assert resp.status_code == 403
