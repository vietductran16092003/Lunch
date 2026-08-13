"""Nghiệp vụ đặt món và thanh toán."""

from ..config import Config, OrderStatus
from ..core.dates import Clock
from ..core.errors import NotFoundError, ValidationError


class OrderService:
    # Hệ thống chỉ còn hình thức chuyển khoản cho người đứng ra đặt
    PAYMENT_METHOD = "transfer"

    def __init__(self, order_repository, menu_repository, user_repository,
                 restaurant_repository, event_broker, config=Config,
                 deadline_service=None, collector_service=None, audit_service=None):
        self.orders = order_repository
        self.menu = menu_repository
        self.users = user_repository
        self.restaurants = restaurant_repository
        self.events = event_broker
        self.config = config
        # Có DeadlineService thì giờ chốt lấy theo từng ngày (mã 4.1); không có
        # thì quay về giờ mặc định trong Config như trước, hành vi không đổi.
        self.deadlines = deadline_service
        self.collectors = collector_service
        self.audit = audit_service

    # ===== Trạng thái vòng đặt của một ngày (mã "chỉ 1 vòng tại 1 thời điểm") =====

    def round_status(self, target_date=None) -> dict:
        """Ngày đó đã có người nhận (CollectorService) chưa, và nếu có thì
        còn đơn nào CHƯA tới trạng thái Hoàn tất hay không — dùng để chặn
        người khác bấm vào "Đặt hàng chung" trong lúc vòng đang dở dang."""
        target_date = Clock.date_or_today(target_date)
        owner = self.collectors.owner_of(target_date) if self.collectors else None

        if owner is None:
            return {"date": target_date, "owner": None, "is_open": False}

        is_open = self.collectors.round_is_open(target_date)

        return {
            "date": target_date,
            "owner": {"id": owner.id, "name": owner.name},
            "is_open": is_open,
        }

    # ===== Kiểm tra chung =====

    def cutoff_for(self, target_date: str) -> str:
        """Giờ chốt "HH:MM" áp dụng cho ngày này (từ DeadlineService nếu có, không thì mặc định hệ thống)."""
        if self.deadlines:
            return self.deadlines.cutoff_for(target_date)
        return self.config.cutoff_label()

    def is_closed(self, target_date: str) -> bool:
        """Ngày này đã quá giờ chốt (hoặc đã qua ngày) chưa."""
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
        """Đặt món mới, hoặc ghi đè đơn đang pending nếu người này đã đặt ngày đó rồi."""
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

    def reorder_from(self, user_id, source_order_id, target_date=None) -> dict:
        """Đặt lại nhanh từ một đơn cũ của chính mình (mã 3.3).

        Món tham chiếu theo menu_item_id của ngày cũ không dùng lại được cho
        ngày mới vì mỗi ngày là một dòng menu_items riêng, nên phải khớp theo
        TÊN món sang thực đơn của target_date. Món hết bán ở ngày mới thì bỏ
        qua (không làm hỏng cả thao tác), báo lại cho người dùng qua
        skipped_items.
        """
        source = self._load_own_order(source_order_id, user_id)
        self.orders.with_items(source)
        target_date = Clock.date_or_today(target_date)

        if not source.items:
            raise ValidationError("Đơn cũ không có món nào để đặt lại")

        names = [i.name for i in source.items if i.name]
        matched_by_name = self.menu.find_matching(names, target_date)

        matched_items = []
        skipped_items = []
        for old_item in source.items:
            key = (old_item.name or "").strip().lower()
            new_item = matched_by_name.get(key)
            if new_item is None:
                skipped_items.append(old_item.name)
                continue
            matched_items.append({
                "menu_item_id": new_item.id,
                "quantity": old_item.quantity,
                "note": old_item.note,
            })

        if not matched_items:
            raise ValidationError("Không còn món nào trong đơn cũ còn bán hôm nay")

        result = self.place_order(user_id, matched_items, target_date)
        result["skipped_items"] = skipped_items
        return result

    def update_order(self, order_id, user_id, items: list) -> dict:
        """Sửa danh sách món của đơn đang pending của chính mình, trước giờ chốt."""
        order = self._load_own_order(order_id, user_id)
        # Giờ chốt tính theo ngày của chính đơn đó, không phải theo hôm nay
        self._assert_open(order.order_date, "sửa đơn")

        if not order.is_pending:
            raise ValidationError("Đơn hàng đã được chốt, không thể sửa")

        self.orders.replace_items(order_id, items or [])
        self.events.publish("order_updated", {"order_id": order_id})
        return {"id": order_id, "status": "updated"}

    def cancel_order(self, order_id, user_id) -> dict:
        """Xoá đơn — dùng chung cho 2 việc khác nhau, mỗi việc một điều kiện:

        1. Nhân viên tự huỷ đơn ĐANG CHỌN MÓN của mình trước giờ chốt (nút
           "Huỷ đơn" ở trang thực đơn) — chỉ được khi còn pending và chưa quá
           giờ chốt, y hệt quy tắc sửa đơn.
        2. Dọn lịch sử: xoá đơn ĐÃ HOÀN TẤT (đã thanh toán) — theo yêu cầu
           nghiệp vụ mới, để dọn bớt đơn cũ đã xong xuôi.

        Đơn đang ở giữa hai trạng thái đó (đã chốt/đang đặt Grab nhưng chưa
        thanh toán xong) thì KHÔNG xoá được ở cả hai trường hợp — đang xử lý dở
        dang, xoá nhầm sẽ mất dấu vết đối soát.
        """
        order = self._load_own_order(order_id, user_id)

        if order.is_pending:
            self._assert_open(order.order_date, "huỷ đơn")
        elif order.status != OrderStatus.COMPLETED:
            raise ValidationError(
                "Đơn đang xử lý dở dang, chỉ huỷ được khi đang chọn món hoặc xoá "
                "được khi đã hoàn tất"
            )

        self.orders.delete(order_id)
        self.events.publish("order_cancelled", {"order_id": order_id})
        return {"status": "deleted"}

    # ===== Xem đơn =====

    def my_order(self, user_id, target_date=None) -> dict:
        """Đơn hiện tại của chính người đang xem cho một ngày, kèm trạng thái giờ chốt."""
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
        """Toàn bộ đơn cũ của một người, mỗi đơn kèm tên người phụ trách ngày đó
        (fallback về admin chính nếu ngày đó không có ai claim, vd đơn cũ trước
        khi có CollectorService)."""
        default_admin = self.users.find_primary_admin()

        history = []
        for order in self.orders.list_for_user(user_id):
            self.orders.with_items(order)
            owner = self.collectors.owner_of(order.order_date) if self.collectors else None
            collector = owner.name if owner else (default_admin.name if default_admin else None)
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

    def confirm_payment(self, order_id, actor_id=None, is_admin=False) -> dict:
        """Người đặt xác nhận đã nhận được tiền của một nhân viên."""
        order = self.orders.find_by_id(order_id)
        if order is None:
            raise NotFoundError("Không tìm thấy đơn hàng")
        if self.collectors:
            self.collectors.authorize_owner_only(actor_id, order.order_date)

        if order.is_pending:
            raise ValidationError("Đơn chưa được chốt")

        if order.is_confirmed:
            self.orders.with_items(order)
            return {"status": "already_confirmed", "order": order.to_dict()}

        now = Clock.now()
        # Nhân viên đưa tiền trực tiếp mà chưa bấm báo thì ghi luôn mốc thanh toán
        self.orders.confirm_payment(order_id, order.paid_at or now, now)
        if self.audit:
            self.audit.log(actor_id, "payment_confirmed", "order", order_id)

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

    def lock_orders(self, target_date=None, actor_id=None, is_admin=False) -> dict:
        """Hành động chính: chốt đơn và trả về link Grab để frontend mở luôn."""
        target_date = Clock.date_or_today(target_date)
        if self.collectors:
            self.collectors.authorize(actor_id, is_admin, target_date)

        locked_count = self.orders.lock_pending_on(target_date, Clock.now())
        # Chỉ lấy quán thật sự có người đặt và có link Grab để mở
        links = [r.to_grab_link() for r in self.restaurants.list_with_orders_on(target_date)]
        if self.audit:
            self.audit.log(actor_id, "orders_locked", "order_date", target_date,
                            details=f"{locked_count} đơn")

        self.events.publish(
            "orders_locked", {"date": target_date, "locked_count": locked_count}
        )

        return {
            "status": OrderStatus.CLOSED,
            "date": target_date,
            "locked_count": locked_count,
            "grab_links": links,
        }

    def clear_date(self, target_date, actor_id=None, is_admin=False) -> dict:
        """Gỡ bỏ hẳn một ngày đã lỡ dựng: xoá thực đơn, mọi đơn và người phụ
        trách của ngày đó. Không cho xoá hôm nay — mọi người đang đặt dở."""
        target_date = Clock.date_or_today(target_date)
        if target_date == Clock.today():
            raise ValidationError("Không xoá được ngày hôm nay")
        if self.collectors:
            self.collectors.authorize(actor_id, is_admin, target_date)

        self.orders.delete_for_date(target_date)
        self.menu.delete_for_date(target_date)
        if self.collectors:
            self.collectors.clear(target_date)
        if self.audit:
            self.audit.log(actor_id, "date_cleared", "order_date", target_date)

        self.events.publish("menu_updated", {"date": target_date, "cleared": True})
        return {"status": "cleared", "date": target_date}

    def mark_grab_placed(self, target_date=None, actor_id=None, is_admin=False) -> dict:
        """Chuyển đơn sang trạng thái chờ thanh toán sau khi đã mở Grab."""
        target_date = Clock.date_or_today(target_date)
        if self.collectors:
            self.collectors.authorize(actor_id, is_admin, target_date)
        updated = self.orders.mark_ordered_on(target_date)

        self.events.publish("orders_ordered", {"date": target_date, "count": updated})
        return {"status": OrderStatus.ORDERED, "date": target_date, "count": updated}
