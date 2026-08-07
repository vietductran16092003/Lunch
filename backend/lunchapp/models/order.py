"""Thực thể đơn hàng và dòng món trong đơn."""

from ..config import OrderStatus
from .base import BaseModel


class OrderItem(BaseModel):
    FIELDS = ("menu_item_id", "name", "price", "quantity", "note")

    def __init__(self, menu_item_id=None, name=None, price=0, quantity=0,
                 image_url=None, restaurant_name=None, note=None):
        self.menu_item_id = menu_item_id
        self.name = name
        self.price = price
        self.quantity = quantity
        self.image_url = image_url
        self.restaurant_name = restaurant_name
        # Ghi chú riêng cho món này, ví dụ "ít cay", "không hành" (mã 3.5)
        self.note = note

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        return cls(
            menu_item_id=cls.column(row, "menu_item_id"),
            name=cls.column(row, "name"),
            price=cls.column(row, "price", 0),
            quantity=cls.column(row, "quantity", 0),
            image_url=cls.column(row, "image_url"),
            restaurant_name=cls.column(row, "restaurant_name"),
            note=cls.column(row, "note"),
        )

    @property
    def line_cost(self):
        return self.price * self.quantity

    def to_dict(self) -> dict:
        return {
            "menu_item_id": self.menu_item_id,
            "name": self.name,
            "price": self.price,
            "quantity": self.quantity,
            "image_url": self.image_url,
            "note": self.note,
        }

    def to_history_dict(self) -> dict:
        """Dạng dùng cho trang lịch sử: kèm sẵn thành tiền và tên quán."""
        return {
            "name": self.name,
            "price": self.price,
            "quantity": self.quantity,
            "line_cost": self.line_cost,
            "restaurant_name": self.restaurant_name,
            "note": self.note,
        }


class Order(BaseModel):
    FIELDS = ("id", "user_id", "order_date", "status", "payment_method")

    def __init__(self, id=None, user_id=None, order_date=None, status=OrderStatus.PENDING,
                 payment_method="transfer", locked_at=None, paid_at=None,
                 payment_confirmed_at=None, items=None, shipping_share=0):
        self.id = id
        self.user_id = user_id
        self.order_date = order_date
        self.status = status
        self.payment_method = payment_method
        self.locked_at = locked_at
        self.paid_at = paid_at
        self.payment_confirmed_at = payment_confirmed_at
        self.items = items or []
        # Phần phí ship chia đều cho đơn này, do coordinator chốt sau khi đặt Grab (mã 4.3)
        self.shipping_share = shipping_share or 0

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        return cls(
            id=cls.column(row, "id"),
            user_id=cls.column(row, "user_id"),
            order_date=cls.column(row, "order_date"),
            status=cls.column(row, "status", OrderStatus.PENDING),
            payment_method=cls.column(row, "payment_method", "transfer"),
            locked_at=cls.column(row, "locked_at"),
            paid_at=cls.column(row, "paid_at"),
            payment_confirmed_at=cls.column(row, "payment_confirmed_at"),
            shipping_share=cls.column(row, "shipping_share", 0),
        )

    # ===== Quy tắc nghiệp vụ =====

    @property
    def items_cost(self):
        return sum(i.line_cost for i in self.items)

    @property
    def total_cost(self):
        """Tổng phải trả: tiền món + phần ship được chia (mã 4.3)."""
        return self.items_cost + self.shipping_share

    @property
    def is_pending(self) -> bool:
        return self.status == OrderStatus.PENDING

    @property
    def is_locked(self) -> bool:
        return self.status in OrderStatus.LOCKED

    @property
    def awaiting_confirmation(self) -> bool:
        """Nhân viên đã báo chuyển khoản nhưng người đặt chưa xác nhận nhận tiền."""
        return bool(self.paid_at) and not self.payment_confirmed_at

    @property
    def is_confirmed(self) -> bool:
        return bool(self.payment_confirmed_at)

    def belongs_to(self, user_id) -> bool:
        return self.user_id == user_id

    def payment_state(self) -> tuple:
        """(mã trạng thái, nhãn hiển thị) cho trang lịch sử."""
        if self.payment_confirmed_at:
            return "confirmed", "Người đặt đã xác nhận nhận tiền"
        if self.paid_at:
            return "awaiting", "Đã chuyển, chờ người đặt xác nhận"
        if self.is_pending:
            return "not_due", "Chưa đến lúc thanh toán"
        return "unpaid", "Chưa thanh toán"

    # ===== Chuyển sang JSON =====

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "order_date": self.order_date,
            "status": self.status,
            "status_label": OrderStatus.label(self.status),
            "step_index": OrderStatus.index(self.status),
            "payment_method": self.payment_method,
            "paid_at": self.paid_at,
            "payment_confirmed_at": self.payment_confirmed_at,
            "awaiting_confirmation": self.awaiting_confirmation,
            "items": [i.to_dict() for i in self.items],
            "items_cost": self.items_cost,
            "shipping_share": self.shipping_share,
            "total_cost": self.total_cost,
        }

    def to_history_dict(self, collector_name=None) -> dict:
        state, label = self.payment_state()
        return {
            "id": self.id,
            "order_date": self.order_date,
            "status": self.status,
            "status_label": OrderStatus.label(self.status),
            "payment_method": self.payment_method,
            "paid_at": self.paid_at,
            "payment_confirmed_at": self.payment_confirmed_at,
            "payment_state": state,
            "payment_label": label,
            "collector_name": collector_name,
            "items": [i.to_history_dict() for i in self.items],
            "items_cost": self.items_cost,
            "shipping_share": self.shipping_share,
            "total_cost": self.total_cost,
        }
