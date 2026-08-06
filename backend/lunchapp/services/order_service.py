"""Nghiệp vụ đặt món và thanh toán."""

from ..config import Config, OrderStatus
from ..core.dates import Clock
from ..core.errors import NotFoundError, ValidationError


class OrderService:
    # Hệ thống chỉ còn hình thức chuyển khoản cho người đứng ra đặt
    PAYMENT_METHOD = "transfer"

    def __init__(self, order_repository, menu_repository, user_repository,
                 restaurant_repository, event_broker, config=Config,
                 deadline_service=None):
        self.orders = order_repository
        self.menu = menu_repository
        self.users = user_repository
        self.restaurants = restaurant_repository
        self.events = event_broker
        self.config = config
        # Có DeadlineService thì giờ chốt lấy theo từng ngày (mã 4.1); không có
        # thì quay về giờ mặc định trong Config như trước, hành vi không đổi.
        self.deadlines = deadline_service

    # ===== Kiểm tra chung =====

    def cutoff_for(self, target_date: str) -> str:
        if self.deadlines:
            return self.deadlines.cutoff_for(target_date)
        return self.config.cutoff_label()

    def is_closed(self, target_date: str) -> bool:
        if self.deadlines:
            return self.deadlines.is_locked(target_date)
        return self.config.cutoff_passed_for(target_date)

    def _assert_open(self, target_date: str, action: str):
        if not self.is_closed(target_date):
            return
        cutoff = self.cutoff_for(target_date)
        if Clock.is_past(target_date):
            message = f"Ngày {target_date} đã qua, không thể {action}"
        else:
            message = f"Đã quá giờ chốt đơn ({cutoff}), không thể {action}"
        raise ValidationError(message, payload={"cutoff": cutoff})

    def _load_own_order(self, order_id, user_id):
        order = self.orders.find_by_id(order_id)
        if order is None or not order.belongs_to(user_id):
            raise NotFoundError("Không tìm thấy đơn hàng")
        return order

    def _employee_name(self, user_id) -> str:
        user = self.users.find_by_id(user_id)
        return user.name if user else "Một nhân viên"

    # ===== Đặt món =====

    def place_order(self, user_id, items: list, order_date=None) -> dict:
        # Cho phép đặt trước cho ngày sau nếu quản trị viên đã lên thực đơn sớm
        target_date = Clock.date_or_today(order_date)
        self._assert_open(target_date, "đặt món")

        requested_ids = [i.get("menu_item_id") for i in (items or []) if i.get("quantity", 0) > 0]
        if not requested_ids:
            raise ValidationError("Vui lòng chọn ít nhất một món")

        # Món phải thuộc đúng thực đơn của ngày được đặt, tránh đặt nhầm ngày
        valid_ids = self.menu.filter_ids_on_date(requested_ids, target_date)
        if set(requested_ids) - valid_ids:
            raise ValidationError(f"Có món không thuộc thực đơn ngày {target_date}")

        # Một người một đơn mỗi ngày: đặt lại thì ghi đè đơn đang chờ
        existing = self.orders.find_for_user_on(user_id, target_date)
        if existing and not existing.is_pending:
            raise ValidationError(
                f"Đơn ngày {target_date} đã được chốt, không thể đặt thêm"
            )

        if existing:
            order_id = existing.id
            self.orders.set_payment_method(order_id, self.PAYMENT_METHOD)
        else:
            order_id = self.orders.create(user_id, target_date, self.PAYMENT_METHOD)

        self.orders.replace_items(order_id, items)

        self.events.publish("order_placed", {
            "order_id": order_id,
            "employee_name": self._employee_name(user_id),
            "item_count": len(items),
            "updated": bool(existing),
            "order_date": target_date,
            "is_advance": target_date != Clock.today(),
        })

        return {"id": order_id, "status": OrderStatus.PENDING, "order_date": target_date}

    def update_order(self, order_id, user_id, items: list) -> dict:
        order = self._load_own_order(order_id, user_id)
        # Giờ chốt tính theo ngày của chính đơn đó, không phải theo hôm nay
        self._assert_open(order.order_date, "sửa đơn")

        if not order.is_pending:
            raise ValidationError("Đơn hàng đã được chốt, không thể sửa")

        self.orders.replace_items(order_id, items or [])
        self.events.publish("order_updated", {"order_id": order_id})
        return {"id": order_id, "status": "updated"}

    def cancel_order(self, order_id, user_id) -> dict:
        order = self._load_own_order(order_id, user_id)
        self._assert_open(order.order_date, "hủy đơn")

        if not order.is_pending:
            raise ValidationError("Đơn hàng đã được chốt, không thể hủy")

        self.orders.delete(order_id)
        self.events.publish("order_cancelled", {"order_id": order_id})
        return {"status": "deleted"}

    # ===== Xem đơn =====

    def my_order(self, user_id, target_date=None) -> dict:
        target_date = Clock.date_or_today(target_date)
        order = self.orders.with_items(self.orders.find_for_user_on(user_id, target_date))

        return {
            "order": order.to_dict() if order else None,
            "date": target_date,
            "is_today": target_date == Clock.today(),
            "cutoff": self.cutoff_for(target_date),
            "cutoff_passed": self.is_closed(target_date),
        }

    def history(self, user_id) -> dict:
        admin = self.users.find_primary_admin()
        collector = admin.name if admin else None

        history = []
        for order in self.orders.list_for_user(user_id):
            self.orders.with_items(order)
            history.append(order.to_history_dict(collector_name=collector))

        return {"history": history}

    # ===== Thanh toán =====

    def declare_payment(self, order_id, user_id) -> dict:
        """Nhân viên báo đã chuyển khoản.

        Chưa tính là xong: đơn chỉ sang "Hoàn tất" khi người đặt xác nhận nhận tiền.
        """
        order = self._load_own_order(order_id, user_id)

        if order.is_pending:
            raise ValidationError("Đơn chưa được chốt, chưa cần thanh toán")

        if order.paid_at:
            self.orders.with_items(order)
            return {"status": "already_declared", "order": order.to_dict()}

        paid_at = Clock.now()
        self.orders.mark_paid(order_id, paid_at)

        refreshed = self.orders.with_items(self.orders.find_by_id(order_id))
        self.events.publish("payment_declared", {
            "order_id": order_id,
            "employee_name": self._employee_name(user_id),
            "amount": refreshed.total_cost,
            "paid_at": paid_at,
        })

        return {"status": "awaiting_confirmation", "order": refreshed.to_dict()}

    def confirm_payment(self, order_id) -> dict:
        """Người đặt xác nhận đã nhận được tiền của một nhân viên."""
        order = self.orders.find_by_id(order_id)
        if order is None:
            raise NotFoundError("Không tìm thấy đơn hàng")

        if order.is_pending:
            raise ValidationError("Đơn chưa được chốt")

        if order.is_confirmed:
            self.orders.with_items(order)
            return {"status": "already_confirmed", "order": order.to_dict()}

        now = Clock.now()
        # Nhân viên đưa tiền trực tiếp mà chưa bấm báo thì ghi luôn mốc thanh toán
        self.orders.confirm_payment(order_id, order.paid_at or now, now)

        refreshed = self.orders.with_items(self.orders.find_by_id(order_id))
        self.events.publish("payment_confirmed", {
            "order_id": order_id,
            "user_id": order.user_id,
            "employee_name": self._employee_name(order.user_id),
            "amount": refreshed.total_cost,
            "confirmed_at": now,
        })

        return {"status": "confirmed", "order": refreshed.to_dict()}

    # ===== Thao tác của người đặt =====

    def lock_orders(self, target_date=None) -> dict:
        """Hành động chính: chốt đơn và trả về link Grab để frontend mở luôn."""
        target_date = Clock.date_or_today(target_date)

        locked_count = self.orders.lock_pending_on(target_date, Clock.now())
        # Chỉ lấy quán thật sự có người đặt và có link Grab để mở
        links = [r.to_grab_link() for r in self.restaurants.list_with_orders_on(target_date)]

        self.events.publish(
            "orders_locked", {"date": target_date, "locked_count": locked_count}
        )

        return {
            "status": OrderStatus.CLOSED,
            "date": target_date,
            "locked_count": locked_count,
            "grab_links": links,
        }

    def mark_grab_placed(self, target_date=None) -> dict:
        """Chuyển đơn sang trạng thái chờ thanh toán sau khi đã mở Grab."""
        target_date = Clock.date_or_today(target_date)
        updated = self.orders.mark_ordered_on(target_date)

        self.events.publish("orders_ordered", {"date": target_date, "count": updated})
        return {"status": OrderStatus.ORDERED, "date": target_date, "count": updated}
