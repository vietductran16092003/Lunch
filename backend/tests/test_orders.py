"""Vòng đời đặt món (mã 3.x). Dùng ngày tương lai để không phụ thuộc giờ chốt thật."""

from datetime import date, timedelta

from .conftest import login, login_employee

FUTURE_DATE = (date.today() + timedelta(days=5)).isoformat()


def _seed_menu_item(container):
    restaurant_id = container.restaurant_repo.list_all()[0].id
    result = container.menu.create_item({
        "name": "Cơm test", "price": 30000,
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_id,
    })
    return result["id"]


def test_place_and_view_order(client, container):
    item_id = _seed_menu_item(container)
    login_employee(client)

    resp = client.post("/api/orders", json={
        "items": [{"menu_item_id": item_id, "quantity": 2}],
        "order_date": FUTURE_DATE,
    })
    assert resp.status_code == 201
    assert resp.get_json()["status"] == "pending"

    resp = client.get(f"/api/orders/my?date={FUTURE_DATE}")
    order = resp.get_json()["order"]
    assert order is not None
    assert order["items"][0]["quantity"] == 2
    assert order["items_cost"] == 60000


def test_cannot_place_empty_order(client, container):
    _seed_menu_item(container)
    login_employee(client)

    resp = client.post("/api/orders", json={"items": [], "order_date": FUTURE_DATE})
    assert resp.status_code == 400


def test_update_order(client, container):
    item_id = _seed_menu_item(container)
    login_employee(client)

    resp = client.post("/api/orders", json={
        "items": [{"menu_item_id": item_id, "quantity": 1}], "order_date": FUTURE_DATE,
    })
    order_id = resp.get_json()["id"]

    resp = client.put(f"/api/orders/{order_id}", json={
        "items": [{"menu_item_id": item_id, "quantity": 3}],
    })
    assert resp.status_code == 200

    resp = client.get(f"/api/orders/my?date={FUTURE_DATE}")
    assert resp.get_json()["order"]["items"][0]["quantity"] == 3


def test_can_cancel_pending_order_before_cutoff(client, container):
    """Nút "Huỷ đơn" ở trang thực đơn — đơn đang chọn món, trước giờ chốt."""
    item_id = _seed_menu_item(container)
    login_employee(client)

    resp = client.post("/api/orders", json={
        "items": [{"menu_item_id": item_id, "quantity": 1}], "order_date": FUTURE_DATE,
    })
    order_id = resp.get_json()["id"]

    resp = client.delete(f"/api/orders/{order_id}")
    assert resp.status_code == 200

    resp = client.get(f"/api/orders/my?date={FUTURE_DATE}")
    assert resp.get_json()["order"] is None


def test_cannot_delete_locked_order_not_yet_completed(client, container):
    """Đơn đã chốt nhưng chưa xác nhận thanh toán — đang xử lý dở dang, không xoá được."""
    item_id = _seed_menu_item(container)
    login_employee(client)

    resp = client.post("/api/orders", json={
        "items": [{"menu_item_id": item_id, "quantity": 1}], "order_date": FUTURE_DATE,
    })
    order_id = resp.get_json()["id"]
    client.post("/api/logout")

    login(client)
    client.post("/api/admin/orders/lock", json={"date": FUTURE_DATE})
    client.post("/api/logout")

    login_employee(client)
    resp = client.delete(f"/api/orders/{order_id}")
    assert resp.status_code == 400


def test_can_delete_completed_order(client, container):
    item_id = _seed_menu_item(container)
    login_employee(client)
    resp = client.post("/api/orders", json={
        "items": [{"menu_item_id": item_id, "quantity": 1}], "order_date": FUTURE_DATE,
    })
    order_id = resp.get_json()["id"]
    # Nhân viên tự nhận ngày này bằng cách thêm món — để tự chốt & xác nhận
    # được luôn (đúng theo quy tắc chỉ người phụ trách mới xác nhận tiền).
    restaurant_id = container.restaurant_repo.list_all()[0].id
    client.post("/api/admin/menu", json={
        "name": "Món phụ", "price": 10000,
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_id,
    })
    client.post("/api/admin/orders/lock", json={"date": FUTURE_DATE})
    client.post(f"/api/admin/orders/{order_id}/confirm-payment")

    resp = client.delete(f"/api/orders/{order_id}")
    assert resp.status_code == 200

    resp = client.get("/api/orders/history")
    assert all(o["id"] != order_id for o in resp.get_json()["history"])


def test_cannot_order_item_from_another_date(client, container):
    item_id = _seed_menu_item(container)
    login_employee(client)

    wrong_date = (date.today() + timedelta(days=6)).isoformat()
    resp = client.post("/api/orders", json={
        "items": [{"menu_item_id": item_id, "quantity": 1}], "order_date": wrong_date,
    })
    assert resp.status_code == 400


def test_employee_cannot_lock_orders_of_someone_elses_day(client, container):
    """Ai đứng ra đặt cho một ngày (ở đây là admin, qua route thật) thì chỉ
    người đó hoặc admin mới chốt được đơn ngày đó — nhân viên khác thì không."""
    restaurant_id = container.restaurant_repo.list_all()[0].id
    login(client)
    client.post("/api/admin/menu", json={
        "name": "Cơm test", "price": 30000,
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_id,
    })
    client.post("/api/logout")

    login_employee(client)
    resp = client.post("/api/admin/orders/lock", json={"date": FUTURE_DATE})
    assert resp.status_code == 403


def test_first_mover_becomes_days_owner(client, container):
    """Nhân viên (không phải admin) thêm món đầu tiên cho một ngày thì tự
    thành người phụ trách ngày đó, và tự chốt được đơn ngày đó."""
    restaurant_id = container.restaurant_repo.list_all()[0].id
    login_employee(client)
    resp = client.post("/api/admin/menu", json={
        "name": "Cơm nhân viên tự đặt", "price": 28000,
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_id,
    })
    assert resp.status_code == 201

    resp = client.post("/api/admin/orders/lock", json={"date": FUTURE_DATE})
    assert resp.status_code == 200


def test_admin_can_lock_and_confirm_payment(client, container):
    """Admin chỉ xác nhận được tiền nếu chính admin là người phụ trách ngày
    đó (thêm món đầu tiên) — không còn đi tắt như các thao tác khác."""
    restaurant_id = container.restaurant_repo.list_all()[0].id
    login(client)
    resp = client.post("/api/admin/menu", json={
        "name": "Cơm test", "price": 30000,
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_id,
    })
    item_id = resp.get_json()["id"]
    client.post("/api/logout")

    login_employee(client)
    resp = client.post("/api/orders", json={
        "items": [{"menu_item_id": item_id, "quantity": 1}], "order_date": FUTURE_DATE,
    })
    order_id = resp.get_json()["id"]
    client.post("/api/logout")

    login(client)
    resp = client.post("/api/admin/orders/lock", json={"date": FUTURE_DATE})
    assert resp.status_code == 200
    assert resp.get_json()["locked_count"] == 1

    resp = client.post(f"/api/admin/orders/{order_id}/confirm-payment")
    assert resp.status_code == 200
    assert resp.get_json()["order"]["status"] == "completed"


def test_non_owner_admin_cannot_confirm_payment(client, container):
    """Ngày do nhân viên phụ trách thì admin cũng không xác nhận tiền được."""
    restaurant_id = container.restaurant_repo.list_all()[0].id
    login_employee(client)
    client.post("/api/admin/menu", json={
        "name": "Cơm nhân viên tự đặt", "price": 28000,
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_id,
    })
    resp = client.post("/api/orders", json={
        "items": [{"menu_item_id": container.menu_items.list_for_date(FUTURE_DATE)[0].id, "quantity": 1}],
        "order_date": FUTURE_DATE,
    })
    order_id = resp.get_json()["id"]
    client.post("/api/admin/orders/lock", json={"date": FUTURE_DATE})
    client.post("/api/logout")

    login(client)
    resp = client.post(f"/api/admin/orders/{order_id}/confirm-payment")
    assert resp.status_code == 403


def test_owner_can_clear_a_future_date(client, container):
    """Nút x ở bảng điều khiển: gỡ hẳn thực đơn + đơn + người phụ trách của
    một ngày đã lỡ dựng."""
    item_id = _seed_menu_item(container)
    login_employee(client)
    resp = client.post("/api/orders", json={
        "items": [{"menu_item_id": item_id, "quantity": 1}], "order_date": FUTURE_DATE,
    })
    order_id = resp.get_json()["id"]

    resp = client.delete(f"/api/admin/orders/day/{FUTURE_DATE}")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "cleared"

    resp = client.get(f"/api/menu?date={FUTURE_DATE}")
    assert resp.get_json()["items"] == []

    resp = client.get(f"/api/orders/round-status?date={FUTURE_DATE}")
    assert resp.get_json()["owner"] is None

    resp = client.get("/api/orders/history")
    assert all(o["id"] != order_id for o in resp.get_json()["history"])


def test_cannot_clear_today(client, container):
    today = date.today().isoformat()
    login(client)
    resp = client.delete(f"/api/admin/orders/day/{today}")
    assert resp.status_code == 400


def test_non_owner_cannot_clear_someone_elses_date(client, container):
    restaurant_id = container.restaurant_repo.list_all()[0].id
    login_employee(client)
    client.post("/api/admin/menu", json={
        "name": "Cơm nhân viên tự đặt", "price": 28000,
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_id,
    })
    client.post("/api/logout")

    client.post("/api/register", json={
        "name": "Nhân viên khác", "email": "khac@fpt.com", "password": "12345678",
    })
    resp = client.delete(f"/api/admin/orders/day/{FUTURE_DATE}")
    assert resp.status_code == 403
