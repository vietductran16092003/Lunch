def test_login_rate_limited_after_threshold(client):
    for _ in range(10):
        client.post("/api/login", json={"email": "admin@fpt.com", "password": "wrong"})

    resp = client.post("/api/login", json={"email": "admin@fpt.com", "password": "wrong"})
    assert resp.status_code == 429


def test_rate_limit_does_not_block_other_bucket(client):
    for _ in range(10):
        client.post("/api/login", json={"email": "admin@fpt.com", "password": "wrong"})

    # Bucket khác (register) không bị ảnh hưởng bởi việc login bị chặn
    resp = client.post("/api/register", json={
        "name": "X", "email": "moi2@fpt.com", "password": "password123",
    })
    assert resp.status_code == 201
