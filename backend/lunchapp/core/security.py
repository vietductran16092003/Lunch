"""Bảo vệ endpoint theo phiên đăng nhập."""

from functools import wraps

from flask import session

from .errors import ForbiddenError, UnauthorizedError


class SessionUser:
    """Đọc/ghi thông tin người đăng nhập trong session Flask."""

    @staticmethod
    def login(user_id: int, is_admin: bool):
        session["user_id"] = user_id
        session["is_admin"] = bool(is_admin)

    @staticmethod
    def logout():
        session.clear()

    @staticmethod
    def id():
        return session.get("user_id")

    @staticmethod
    def is_admin() -> bool:
        return bool(session.get("is_admin"))

    @classmethod
    def require_id(cls) -> int:
        user_id = cls.id()
        if not user_id:
            raise UnauthorizedError("Chưa đăng nhập")
        return user_id


def require_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        SessionUser.require_id()
        return f(*args, **kwargs)

    return wrapper


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        SessionUser.require_id()
        if not SessionUser.is_admin():
            raise ForbiddenError("Chỉ quản trị viên mới được thực hiện thao tác này")
        return f(*args, **kwargs)

    return wrapper
