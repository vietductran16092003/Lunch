from .conftest import login, login_employee


def test_login_success(client):
    resp = login(client)
    assert resp.status_code == 200
    assert resp.get_json()["email"] == "admin@fpt.com"


def test_login_wrong_password(client):
    resp = client.post("/api/login", json={"email": "admin@fpt.com", "password": "wrong"})
    assert resp.status_code == 401


def test_me_requires_login(client):
    resp = client.get("/api/me")
    assert resp.status_code == 401


def test_me_after_login(client):
    login(client)
    resp = client.get("/api/me")
    assert resp.status_code == 200
    assert resp.get_json()["email"] == "admin@fpt.com"


def test_register_rejects_disallowed_domain(client):
    resp = client.post("/api/register", json={
        "name": "X", "email": "x@gmail.com", "password": "password123",
    })
    assert resp.status_code == 400


def test_register_allowed_domain(client):
    resp = client.post("/api/register", json={
        "name": "Người mới", "email": "moi@fpt.com", "password": "password123",
    })
    assert resp.status_code == 201
    assert resp.get_json()["roles"] == ["employee"]


def test_employee_login(client):
    resp = login_employee(client)
    assert resp.status_code == 200
    assert resp.get_json()["roles"] == ["employee"]


def test_admin_can_delete_user(client):
    login(client)
    client.post("/api/register", json={
        "name": "Xoa test", "email": "xoatest@fpt.com", "password": "password123",
    })
    login(client)  # register() logs the new account in; switch back to admin

    resp = client.get("/api/admin/users")
    target = next(u for u in resp.get_json()["users"] if u["email"] == "xoatest@fpt.com")

    resp = client.delete(f"/api/admin/users/{target['id']}")
    assert resp.status_code == 200

    resp = client.get("/api/admin/users")
    assert all(u["email"] != "xoatest@fpt.com" for u in resp.get_json()["users"])


def test_cannot_delete_self(client):
    login(client)
    resp = client.get("/api/admin/users")
    admin_id = next(u["id"] for u in resp.get_json()["users"] if u["email"] == "admin@fpt.com")

    resp = client.delete(f"/api/admin/users/{admin_id}")
    assert resp.status_code == 409


def test_cannot_delete_user_with_orders(client, container):
    login(client)
    restaurant_id = container.restaurant_repo.list_all()[0].id
    item_id = container.menu.create_item({
        "name": "Del guard", "price": 10000,
        "available_date": "2030-01-01", "restaurant_id": restaurant_id,
    })["id"]

    login_employee(client)
    client.post("/api/orders", json={
        "items": [{"menu_item_id": item_id, "quantity": 1}], "order_date": "2030-01-01",
    })

    login(client)
    resp = client.get("/api/admin/users")
    employee_id = next(u["id"] for u in resp.get_json()["users"] if u["email"] == "nhanvien@fpt.com")

    resp = client.delete(f"/api/admin/users/{employee_id}")
    assert resp.status_code == 409
