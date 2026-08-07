from datetime import date, timedelta

from .conftest import login, login_employee

FUTURE_DATE = (date.today() + timedelta(days=5)).isoformat()


def test_create_and_vote_poll(client):
    login(client)
    resp = client.post("/api/polls", json={
        "question": "Ăn gì?", "options": ["Quán A", "Quán B"], "poll_date": FUTURE_DATE,
    })
    assert resp.status_code == 201
    poll = resp.get_json()["poll"]
    option_id = poll["options"][0]["id"]
    client.post("/api/logout")

    login_employee(client)
    resp = client.post(f"/api/polls/{poll['id']}/vote", json={"option_id": option_id})
    assert resp.status_code == 200
    data = resp.get_json()["poll"]
    assert data["total_votes"] == 1
    assert data["voted_option_id"] == option_id


def test_cannot_create_poll_with_one_option(client):
    login(client)
    resp = client.post("/api/polls", json={
        "question": "?", "options": ["Chỉ một"], "poll_date": FUTURE_DATE,
    })
    assert resp.status_code == 400


def test_employee_cannot_create_poll(client):
    login_employee(client)
    resp = client.post("/api/polls", json={
        "question": "?", "options": ["A", "B"], "poll_date": FUTURE_DATE,
    })
    assert resp.status_code == 403


def test_closed_poll_rejects_vote(client):
    login(client)
    resp = client.post("/api/polls", json={
        "question": "?", "options": ["A", "B"], "poll_date": FUTURE_DATE,
    })
    poll = resp.get_json()["poll"]
    client.post(f"/api/polls/{poll['id']}/close")

    resp = client.post(f"/api/polls/{poll['id']}/vote", json={"option_id": poll["options"][0]["id"]})
    assert resp.status_code == 400
