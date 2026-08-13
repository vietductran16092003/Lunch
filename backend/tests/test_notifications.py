from .conftest import login, login_employee


def test_broadcast_creates_notification_for_everyone(client):
    login(client)
    client.post("/api/coordinator/broadcast", json={"message": "Nghỉ lễ tuần sau"})
    client.post("/api/logout")

    login_employee(client)
    resp = client.get("/api/notifications")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["unread_count"] >= 1
    assert any(n["message"] == "Nghỉ lễ tuần sau" for n in data["notifications"])


def test_mark_read_reduces_unread_count(client):
    login(client)
    client.post("/api/coordinator/broadcast", json={"message": "Thông báo test"})

    resp = client.get("/api/notifications")
    before = resp.get_json()["unread_count"]
    notif_id = next(
        n["id"] for n in resp.get_json()["notifications"] if n["message"] == "Thông báo test"
    )

    resp = client.post(f"/api/notifications/{notif_id}/read")
    assert resp.status_code == 200

    resp = client.get("/api/notifications")
    after = resp.get_json()["unread_count"]
    assert after == before - 1


def test_password_reset_request_only_visible_to_admin(client):
    resp = client.post("/api/password/forgot", json={"email": "nhanvien@fpt.com"})
    assert resp.status_code == 200
    assert "reset_token" not in resp.get_json()

    login_employee(client)
    resp = client.get("/api/notifications")
    assert not any(n["type"] == "password_reset_requested" for n in resp.get_json()["notifications"])
    client.post("/api/logout")

    login(client)
    resp = client.get("/api/notifications")
    assert any(n["type"] == "password_reset_requested" for n in resp.get_json()["notifications"])


def test_mark_all_read(client):
    login(client)
    client.post("/api/coordinator/broadcast", json={"message": "A"})
    client.post("/api/coordinator/broadcast", json={"message": "B"})

    resp = client.post("/api/notifications/read-all")
    assert resp.status_code == 200

    resp = client.get("/api/notifications")
    assert resp.get_json()["unread_count"] == 0
