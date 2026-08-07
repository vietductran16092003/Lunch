from datetime import date, timedelta

from .conftest import login, login_employee


def _place_order(client, container, order_date, item_name="Món ngày cũ"):
    restaurant_id = container.restaurant_repo.list_all()[0].id
    item_id = container.menu.create_item({
        "name": item_name, "price": 20000,
        "available_date": order_date, "restaurant_id": restaurant_id,
    })["id"]
    login_employee(client)
    client.post("/api/orders", json={
        "items": [{"menu_item_id": item_id, "quantity": 1}], "order_date": order_date,
    })
    client.post("/api/logout")


def test_predict_with_no_history_reports_no_data(client):
    login(client)
    future = (date.today() + timedelta(days=5)).isoformat()
    resp = client.get(f"/api/ai/predict?date={future}")
    assert resp.status_code == 200
    assert resp.get_json()["has_data"] is False


def test_predict_uses_same_weekday_history(client, container):
    # Cùng thứ trong tuần, cách nhau đúng 7 ngày để chắc chắn khớp weekday
    target = date.today() + timedelta(days=14)
    same_weekday_past = target - timedelta(days=7)
    _place_order(client, container, same_weekday_past.isoformat())

    login(client)
    resp = client.get(f"/api/ai/predict?date={target.isoformat()}")
    body = resp.get_json()
    assert body["has_data"] is True
    assert body["predicted_orders"] == 1
    assert body["likely_items"][0]["name"] == "Món ngày cũ"


def test_employee_cannot_predict(client):
    login_employee(client)
    resp = client.get("/api/ai/predict")
    assert resp.status_code == 403
