"""Bảo vệ endpoint theo phiên đăng nhập."""

from functools import wraps

from flask import session

from .errors import ForbiddenError, UnauthorizedError
from .roles import Role


class SessionUser:
    """Đọc/ghi thông tin người đăng nhập trong session Flask."""

    @staticmethod
    def login(user_id: int, is_admin: bool = False, roles=None):
        session["user_id"] = user_id
        stored = Role.sort(roles) if roles is not None else Role.for_admin_flag(is_admin)
        session["roles"] = stored
        # Vẫn ghi is_admin để cookie phiên đọc được bởi code cũ, nhưng nguồn sự
        # thật khi kiểm tra quyền là danh sách roles ở trên.
        session["is_admin"] = Role.ADMIN in stored

    @staticmethod
    def logout():
        session.clear()

    @staticmethod
    def id():
        return session.get("user_id")

    @staticmethod
    def roles() -> list:
        """Cookie phát hành trước khi có phân quyền đa vai trò thì không có khoá
        `roles`; khi đó suy tạm từ is_admin để người dùng không bị đá ra."""
        stored = session.get("roles")
        if stored is None:
            return Role.for_admin_flag(session.get("is_admin"))
        return Role.sort(stored)

    @classmethod
    def has_role(cls, role) -> bool:
        return role in cls.roles()

    @classmethod
    def has_any(cls, *roles) -> bool:
        if not roles:
            return True
        current = set(cls.roles())
        return any(role in current for role in roles)

    @classmethod
    def is_admin(cls) -> bool:
        return cls.has_role(Role.ADMIN)

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


def require_role(*roles):
    """Cho qua nếu người dùng giữ ÍT NHẤT MỘT trong các vai trò liệt kê.

    Hầu hết thao tác đều mở cho vài vai trò (ví dụ điều phối hoặc quản trị), nên
    ngữ nghĩa "hoặc" tiện hơn "và"; cần "và" thì chồng nhiều decorator.
    """
    required = tuple(roles)

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            SessionUser.require_id()
            if not SessionUser.has_any(*required):
                labels = ", ".join(Role.label(role) for role in required)
                raise ForbiddenError(f"Thao tác này chỉ dành cho: {labels}")
            return f(*args, **kwargs)

        return wrapper

    return decorator


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        SessionUser.require_id()
        if not SessionUser.has_role(Role.ADMIN):
            raise ForbiddenError("Chỉ quản trị viên mới được thực hiện thao tác này")
        return f(*args, **kwargs)

    return wrapper
