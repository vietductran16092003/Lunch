"""Lỗi nghiệp vụ.

Tầng service ném các lỗi này, tầng API bắt một chỗ duy nhất và đổi thành JSON.
Nhờ vậy service không cần biết gì về Flask.
"""


class AppError(Exception):
    """Lỗi có thể hiển thị thẳng cho người dùng."""

    status_code = 400

    def __init__(self, message: str, status_code: int | None = None, payload: dict | None = None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload or {}

    def to_dict(self) -> dict:
        return {"error": self.message, **self.payload}


class ValidationError(AppError):
    status_code = 400


class UnauthorizedError(AppError):
    status_code = 401


class ForbiddenError(AppError):
    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409
