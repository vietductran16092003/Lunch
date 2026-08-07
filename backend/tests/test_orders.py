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


def test_update_and_cancel_order(client, container):
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

    resp = client.delete(f"/api/orders/{order_id}")
    assert resp.status_code == 200

    resp = client.get(f"/api/orders/my?date={FUTURE_DATE}")
    assert resp.get_json()["order"] is None


def test_cannot_order_item_from_another_date(client, container):
    item_id = _seed_menu_item(container)
    login_employee(client)

    wrong_date = (date.today() + timedelta(days=6)).isoformat()
    resp = client.post("/api/orders", json={
        "items": [{"menu_item_id": item_id, "quantity": 1}], "order_date": wrong_date,
    })
    assert resp.status_code == 400


def test_employee_cannot_lock_orders(client, container):
    _seed_menu_item(container)
    login_employee(client)

    resp = client.post("/api/admin/orders/lock", json={"date": FUTURE_DATE})
    assert resp.status_code == 403


def test_admin_can_lock_and_confirm_payment(client, container):
    item_id = _seed_menu_item(container)
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
