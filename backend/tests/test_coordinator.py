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


def test_place_order_for_employee(client, container):
    item_id = _seed_menu_item(container)
    login(client)

    resp = client.get("/api/coordinator/employees")
    employee = next(u for u in resp.get_json()["users"] if u["email"] == "nhanvien@fpt.com")

    resp = client.post(f"/api/coordinator/orders-for/{employee['id']}", json={
        "items": [{"menu_item_id": item_id, "quantity": 1}], "order_date": FUTURE_DATE,
    })
    assert resp.status_code == 201

    client.post("/api/logout")
    login_employee(client)
    resp = client.get(f"/api/orders/my?date={FUTURE_DATE}")
    assert resp.get_json()["order"] is not None


def test_grouped_by_restaurant(client, container):
    item_id = _seed_menu_item(container)
    login_employee(client)
    client.post("/api/orders", json={
        "items": [{"menu_item_id": item_id, "quantity": 2}], "order_date": FUTURE_DATE,
    })
    client.post("/api/logout")

    login(client)
    resp = client.get(f"/api/coordinator/grouped?date={FUTURE_DATE}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["grand_total"] == 60000


def test_broadcast_requires_message(client):
    login(client)
    resp = client.post("/api/coordinator/broadcast", json={"message": ""})
    assert resp.status_code == 400


def test_broadcast_success(client):
    login(client)
    resp = client.post("/api/coordinator/broadcast", json={"message": "Xin chào"})
    assert resp.status_code == 200
