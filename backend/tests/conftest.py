"""Fixture dùng chung: mỗi test chạy trên một database SQLite tạm, tự xoá sau khi xong."""

import os
import tempfile

import pytest

from lunchapp import Config, create_app
from lunchapp.container import ServiceContainer
from lunchapp.core.database import Database
from lunchapp.core.events import EventBroker
from lunchapp.core.rate_limit import limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Bộ đếm rate limit sống ở biến toàn cục process, phải xoá giữa các test
    để test này không bị tính hạn mức do test trước để lại."""
    limiter._hits.clear()
    yield


class TestConfig(Config):
    SECRET_KEY = "test-secret"
    DEBUG = False


@pytest.fixture
def container():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    db = Database(path)
    db.init_schema()
    c = ServiceContainer(db, EventBroker(), TestConfig)
    yield c

    os.unlink(path)


@pytest.fixture
def app(container):
    return create_app(TestConfig, container)


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email="admin@fpt.com", password="admin123"):
    """Tài khoản admin có sẵn từ dữ liệu mẫu (_seed_demo_data)."""
    return client.post("/api/login", json={"email": email, "password": password})


def login_employee(client):
    return login(client, "nhanvien@fpt.com", "123456")
