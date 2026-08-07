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
