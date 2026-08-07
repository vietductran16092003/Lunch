"""Luồng 2: thủ quỹ trả đơn bằng quỹ chung + góp quỹ hàng tháng."""

from datetime import date, timedelta

from .conftest import login, login_employee

FUTURE_DATE = (date.today() + timedelta(days=5)).isoformat()


def _seed_locked_order(client, container):
    restaurant_id = container.restaurant_repo.list_all()[0].id
    item_id = container.menu.create_item({
        "name": "Cơm quỹ", "price": 40000,
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_id,
    })["id"]

    login_employee(client)
    client.post("/api/orders", json={
        "items": [{"menu_item_id": item_id, "quantity": 1}], "order_date": FUTURE_DATE,
    })
    client.post("/api/logout")

    login(client)
    client.post("/api/admin/orders/lock", json={"date": FUTURE_DATE})
    client.post("/api/fund/topup", json={"amount": 200000, "note": "seed"})


def test_pay_orders_from_fund(client, container):
    _seed_locked_order(client, container)

    resp = client.post("/api/fund/pay-from-fund", json={"date": FUTURE_DATE})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["order_count"] == 1
    assert body["total_paid"] == 40000
    assert body["balance"] == 160000

    client.post("/api/logout")
    login_employee(client)
    resp = client.get(f"/api/orders/my?date={FUTURE_DATE}")
    order = resp.get_json()["order"]
    assert order["status"] == "completed"
    assert order["payment_method"] == "fund"


def test_pay_from_fund_fails_when_balance_insufficient(client, container):
    restaurant_id = container.restaurant_repo.list_all()[0].id
    item_id = container.menu.create_item({
        "name": "Cơm đắt", "price": 5_000_000,
        "available_date": FUTURE_DATE, "restaurant_id": restaurant_id,
    })["id"]

    login_employee(client)
    client.post("/api/orders", json={
        "items": [{"menu_item_id": item_id, "quantity": 1}], "order_date": FUTURE_DATE,
    })
    client.post("/api/logout")

    login(client)
    client.post("/api/admin/orders/lock", json={"date": FUTURE_DATE})
    resp = client.post("/api/fund/pay-from-fund", json={"date": FUTURE_DATE})
    assert resp.status_code == 400


def test_pay_from_fund_requires_no_pending_orders(client):
    login(client)
    resp = client.post("/api/fund/pay-from-fund", json={"date": FUTURE_DATE})
    assert resp.status_code == 400


def test_employee_cannot_pay_from_fund(client):
    login_employee(client)
    resp = client.post("/api/fund/pay-from-fund", json={"date": FUTURE_DATE})
    assert resp.status_code == 403


def test_contribute_dues_and_overview(client):
    login(client)
    resp = client.get("/api/coordinator/employees")
    employee = next(u for u in resp.get_json()["users"] if u["email"] == "nhanvien@fpt.com")

    resp = client.post("/api/fund/dues", json={
        "user_id": employee["id"], "amount": 100000, "month": "2026-08",
    })
    assert resp.status_code == 201
    assert resp.get_json()["balance"] == 100000

    resp = client.get("/api/fund/dues?month=2026-08")
    overview = resp.get_json()
    assert overview["total_collected"] == 100000
    assert len(overview["contributed"]) == 1
    assert all(u["email"] != "nhanvien@fpt.com" for u in overview["pending"])


def test_cannot_contribute_dues_twice_same_month(client):
    login(client)
    resp = client.get("/api/coordinator/employees")
    employee = next(u for u in resp.get_json()["users"] if u["email"] == "nhanvien@fpt.com")

    client.post("/api/fund/dues", json={
        "user_id": employee["id"], "amount": 100000, "month": "2026-08",
    })
    resp = client.post("/api/fund/dues", json={
        "user_id": employee["id"], "amount": 50000, "month": "2026-08",
    })
    assert resp.status_code == 400


def test_invalid_month_format_rejected(client):
    login(client)
    resp = client.post("/api/fund/dues", json={"user_id": 2, "amount": 100000, "month": "08-2026"})
    assert resp.status_code == 400


def test_treasurer_role_can_list_employees(client, container):
    from lunchapp.core.roles import Role
    container.users.replace_roles(2, [Role.EMPLOYEE])  # no-op sanity: user 2 stays employee

    # Đăng ký một tài khoản treasurer để kiểm tra quyền xem danh bạ nhân viên
    client.post("/api/register", json={
        "name": "Thu quy test", "email": "thuquytest@fpt.com", "password": "password123",
    })
    admin_user = container.users.find_by_email("thuquytest@fpt.com")
    container.users.replace_roles(admin_user.id, [Role.TREASURER])
    client.post("/api/logout")

    client.post("/api/login", json={"email": "thuquytest@fpt.com", "password": "password123"})
    resp = client.get("/api/coordinator/employees")
    assert resp.status_code == 200
