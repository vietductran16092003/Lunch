from datetime import date

from .conftest import login, login_employee

TODAY = date.today().isoformat()


def test_chat_answers_menu_question(client):
    login_employee(client)
    resp = client.post("/api/ai/chat", json={"message": "hôm nay có gì"})
    assert resp.status_code == 200
    assert "reply" in resp.get_json()


def test_chat_answers_cutoff_question(client):
    login_employee(client)
    resp = client.post("/api/ai/chat", json={"message": "giờ chốt đơn"})
    body = resp.get_json()
    assert "11:00" in body["reply"]


def test_summary_requires_role(client):
    login_employee(client)
    resp = client.get(f"/api/ai/summary?date={TODAY}")
    assert resp.status_code == 403


def test_summary_for_coordinator(client):
    login(client)  # admin cũng mang vai trò coordinator theo seed data
    resp = client.get(f"/api/ai/summary?date={TODAY}")
    assert resp.status_code == 200
    assert "summary_text" in resp.get_json()


def test_suggestions_returns_list(client):
    login_employee(client)
    resp = client.get(f"/api/ai/suggestions?date={TODAY}")
    assert resp.status_code == 200
    assert "suggestions" in resp.get_json()


def test_report_rejects_invalid_range(client):
    login(client)
    resp = client.get(f"/api/ai/report?start={TODAY}&end=2020-01-01")
    assert resp.status_code == 400
