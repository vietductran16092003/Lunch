"""Danh mục vai trò của người dùng.

Trước đây quyền hạn chỉ có cờ nhị phân `is_admin`, nên không diễn tả được thực
tế: người lo lịch đặt cơm (điều phối) và người thu tiền thường là hai người khác
nhau, và không ai trong họ nhất thiết phải là quản trị viên. Gom tên vai trò vào
một nơi để tầng service, repository và API không ai tự viết chuỗi rời rạc.
"""

EMPLOYEE = "employee"
COORDINATOR = "coordinator"
TREASURER = "treasurer"
ADMIN = "admin"


class Role:
    """Hằng số vai trò kèm nhãn hiển thị và helper kiểm tra hợp lệ."""

    EMPLOYEE = EMPLOYEE
    COORDINATOR = COORDINATOR
    TREASURER = TREASURER
    ADMIN = ADMIN

    # Thứ tự trong ALL cũng là thứ tự chuẩn hoá khi trả về cho frontend, để
    # danh sách vai trò của một người luôn hiện cùng một trật tự.
    ALL = (EMPLOYEE, COORDINATOR, TREASURER, ADMIN)

    LABELS = {
        EMPLOYEE: "Nhân viên",
        COORDINATOR: "Người điều phối",
        TREASURER: "Thủ quỹ",
        ADMIN: "Quản trị viên",
    }

    @classmethod
    def is_valid(cls, role) -> bool:
        return role in cls.ALL

    @classmethod
    def label(cls, role) -> str:
        return cls.LABELS.get(role, str(role))

    @classmethod
    def normalize(cls, role) -> str | None:
        """Trả về vai trò chuẩn, hoặc None nếu chuỗi không thuộc danh mục."""
        value = str(role or "").strip().lower()
        return value if cls.is_valid(value) else None

    @classmethod
    def sort(cls, roles) -> list:
        """Sắp theo thứ tự ALL và bỏ trùng, để so sánh/hiển thị luôn ổn định."""
        unique = {r for r in (roles or []) if cls.is_valid(r)}
        return [r for r in cls.ALL if r in unique]

    @classmethod
    def clean_many(cls, roles) -> list:
        """Chuẩn hoá cả danh sách; ném lỗi ở tầng gọi nếu có phần tử lạ."""
        return cls.sort([cls.normalize(r) for r in (roles or [])])

    @classmethod
    def invalid_items(cls, roles) -> list:
        """Liệt kê phần tử không hợp lệ để báo lỗi cho người dùng biết sai ở đâu."""
        return [r for r in (roles or []) if cls.normalize(r) is None]

    @classmethod
    def for_admin_flag(cls, is_admin) -> list:
        """Suy vai trò từ cờ is_admin cũ — dùng cho migration và cho các bản ghi
        User đọc lên từ câu SELECT không kèm cột roles."""
        if is_admin:
            return list(cls.ALL)
        return [cls.EMPLOYEE]
