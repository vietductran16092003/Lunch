"""Nghiệp vụ quỹ chung: số dư, nạp/rút, công nợ và chia phí ship."""

from ..config import Config
from ..core.dates import Clock
from ..core.errors import ValidationError


class FundService:
    """Toàn bộ tiền dùng integer (đơn vị đồng), không dùng float."""

    def __init__(self, fund_repository, order_repository, user_repository,
                 event_broker, config=Config):
        self.fund = fund_repository
        self.orders = order_repository
        self.users = user_repository
        self.events = event_broker
        self.config = config

    # ===== Số dư & sổ quỹ (5.3, 5.4) =====

    def balance(self) -> dict:
        return {"balance": self.fund.get_balance()}

    def ledger(self, limit: int = 100) -> dict:
        return {"transactions": [tx.to_dict() for tx in self.fund.list_transactions(limit)]}

    # ===== Nạp / rút quỹ (5.5) =====

    def _validate_amount(self, amount) -> int:
        try:
            amount = int(amount)
        except (TypeError, ValueError):
            raise ValidationError("Số tiền không hợp lệ")
        if amount <= 0:
            raise ValidationError("Số tiền phải lớn hơn 0")
        return amount

    def topup(self, user_id, amount, note: str = "") -> dict:
        amount = self._validate_amount(amount)
        self.fund.record_transaction("topup", amount, user_id, (note or "").strip() or None,
                                      Clock.now())
        new_balance = self.fund.get_balance()

        self.events.publish("fund_updated", {
            "type": "topup", "amount": amount, "balance": new_balance,
        })
        return {"status": "topup", "amount": amount, "balance": new_balance}

    def withdraw(self, user_id, amount, note: str = "") -> dict:
        amount = self._validate_amount(amount)
        current_balance = self.fund.get_balance()
        # Quy tắc nghiệp vụ quan trọng nhất: không cho rút quá số dư hiện có
        if amount > current_balance:
            raise ValidationError("Số dư quỹ không đủ")

        self.fund.record_transaction("deduct", amount, user_id, (note or "").strip() or None,
                                      Clock.now())
        new_balance = self.fund.get_balance()

        self.events.publish("fund_updated", {
            "type": "deduct", "amount": amount, "balance": new_balance,
        })
        return {"status": "deduct", "amount": amount, "balance": new_balance}

    # ===== Công nợ (5.6) =====

    def debts(self, since_date: str | None = None) -> dict:
        """Tổng nợ từng người từ các đơn đã chốt nhưng chưa xác nhận thanh toán.

        Gộp theo order_id trước để lấy shipping_share đúng một lần mỗi đơn (một
        đơn có nhiều dòng order_item sẽ lặp lại shipping_share nếu gộp thẳng),
        rồi mới gộp tiếp theo user_id để ra tổng nợ từng người.
        """
        rows = self.orders.unconfirmed_rows(since_date)

        orders_by_id = {}
        for row in rows:
            order_id = row["order_id"]
            entry = orders_by_id.get(order_id)
            if entry is None:
                entry = {
                    "order_id": order_id,
                    "order_date": row["order_date"],
                    "user_id": row["user_id"],
                    "user_name": row["user_name"],
                    "items_cost": 0,
                    "shipping_share": row["shipping_share"] or 0,
                }
                orders_by_id[order_id] = entry
            entry["items_cost"] += row["price"] * row["quantity"]

        debts_by_user = {}
        for entry in orders_by_id.values():
            amount = entry["items_cost"] + entry["shipping_share"]
            user_id = entry["user_id"]
            bucket = debts_by_user.get(user_id)
            if bucket is None:
                bucket = {
                    "user_id": user_id,
                    "user_name": entry["user_name"],
                    "total_owed": 0,
                    "orders": [],
                }
                debts_by_user[user_id] = bucket
            bucket["total_owed"] += amount
            bucket["orders"].append({
                "order_id": entry["order_id"],
                "order_date": entry["order_date"],
                "amount": amount,
            })

        debts = sorted(debts_by_user.values(), key=lambda d: d["total_owed"], reverse=True)
        grand_total = sum(d["total_owed"] for d in debts)
        return {"debts": debts, "grand_total": grand_total}

    # ===== Chia phí ship (4.3) =====

    def split_shipping(self, target_date, total_fee, actor_id=None) -> dict:
        """Chia đều phí ship của một ngày cho các đơn ĐÃ CHỐT trở lên.

        Đơn còn `pending` không được tính vì người đặt có thể còn đổi món/huỷ.
        Chia không hết thì số dư lẻ dồn hết vào đơn có id nhỏ nhất (đặt trước) —
        đây là quyết định nghiệp vụ đơn giản và dễ giải thích nhất.
        """
        target_date = Clock.parse_date(target_date)
        if target_date is None:
            raise ValidationError("Ngày không hợp lệ, cần định dạng YYYY-MM-DD")

        try:
            total_fee = int(total_fee)
        except (TypeError, ValueError):
            raise ValidationError("Phí ship không hợp lệ")
        if total_fee <= 0:
            raise ValidationError("Phí ship phải lớn hơn 0")

        all_orders = self.orders.list_for_date(target_date)
        locked_orders = sorted((o for o in all_orders if o.is_locked), key=lambda o: o.id)

        if not locked_orders:
            raise ValidationError("Chưa có đơn nào được chốt trong ngày này để chia ship")

        count = len(locked_orders)
        base_share = total_fee // count
        remainder = total_fee % count

        shares = {}
        for index, order in enumerate(locked_orders):
            shares[order.id] = base_share + (remainder if index == 0 else 0)

        self.orders.set_shipping_shares(shares)

        self.events.publish("shipping_split", {
            "date": target_date, "total_fee": total_fee, "order_count": count,
        })

        order_details = []
        for order in locked_orders:
            user = self.users.find_by_id(order.user_id)
            order_details.append({
                "order_id": order.id,
                "user_name": user.name if user else None,
                "shipping_share": shares[order.id],
            })

        return {
            "date": target_date,
            "total_fee": total_fee,
            "per_order": base_share,
            "order_count": count,
            "orders": order_details,
        }
