from .conftest import login, login_employee


def test_employee_cannot_see_fund(client):
    login_employee(client)
    resp = client.get("/api/fund/balance")
    assert resp.status_code == 403


def test_topup_and_withdraw(client):
    login(client)

    resp = client.post("/api/fund/topup", json={"amount": 500000, "note": "Nạp đầu tháng"})
    assert resp.status_code == 200
    assert resp.get_json()["balance"] == 500000

    resp = client.post("/api/fund/withdraw", json={"amount": 200000, "note": "Trả quán"})
    assert resp.status_code == 200
    assert resp.get_json()["balance"] == 300000

    resp = client.get("/api/fund/ledger")
    transactions = resp.get_json()["transactions"]
    assert len(transactions) == 2


def test_cannot_withdraw_more_than_balance(client):
    login(client)
    client.post("/api/fund/topup", json={"amount": 100000})

    resp = client.post("/api/fund/withdraw", json={"amount": 999999})
    assert resp.status_code == 400


def test_cannot_topup_negative_amount(client):
    login(client)
    resp = client.post("/api/fund/topup", json={"amount": -100})
    assert resp.status_code == 400
