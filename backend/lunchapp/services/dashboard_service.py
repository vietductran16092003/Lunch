"""Tổng hợp dữ liệu cho bảng điều khiển của người đứng ra đặt."""

from ..config import Config, OrderStatus
from ..core.dates import Clock


class EmployeeOrderSummary:
    """Gộp nhiều dòng món của cùng một nhân viên thành một bản ghi."""

    def __init__(self, row):
        self.order_id = row["order_id"]
        self.employee_name = row["employee_name"]
        self.employee_email = row["employee_email"]
        self.status = row["status"]
        self.paid_at = row["paid_at"]
        self.payment_confirmed_at = row["payment_confirmed_at"]
        # Phương thức thanh toán chỉ lộ ra sau khi đơn đã chốt — trước đó nhân
        # viên vẫn có thể đổi ý nên chưa cần biết
        self._payment_method = row["payment_method"] if self.revealed else None
        self.items = []
        self.total_cost = 0

    @property
    def revealed(self) -> bool:
        return self.status in OrderStatus.LOCKED

    @property
    def confirmed(self) -> bool:
        return bool(self.payment_confirmed_at)

    @property
    def awaiting_confirmation(self) -> bool:
        return bool(self.paid_at) and not self.payment_confirmed_at

    def add_line(self, row):
        line_cost = row["price"] * row["quantity"]
        self.items.append({
            "item_name": row["item_name"],
            "price": row["price"],
            "quantity": row["quantity"],
            "line_cost": line_cost,
        })
        self.total_cost += line_cost

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "employee_name": self.employee_name,
            "employee_email": self.employee_email,
            "status": self.status,
            "status_label": OrderStatus.label(self.status),
            "payment_method": self._payment_method,
            "paid": bool(self.paid_at),
            "paid_at": self.paid_at,
            "confirmed": self.confirmed,
            "payment_confirmed_at": self.payment_confirmed_at,
            "awaiting_confirmation": self.awaiting_confirmation,
            "items": self.items,
            "total_cost": self.total_cost,
        }


class DashboardService:
    """Một nguồn dữ liệu duy nhất thay cho hai màn hình tổng hợp và chi tiết cũ."""

    def __init__(self, order_repository, restaurant_repository, config=Config):
        self.orders = order_repository
        self.restaurants = restaurant_repository
        self.config = config

    def build(self, target_date=None) -> dict:
        target_date = Clock.date_or_today(target_date)
        today = Clock.today()

        summary = [dict(r) for r in self.orders.summary_by_item(target_date)]
        employees = self._group_by_employee(self.orders.rows_by_employee(target_date))
        counts = self.orders.status_counts(target_date)

        return {
            "date": target_date,
            "today": today,
            "is_today": target_date == today,
            # Ngày có thực đơn hoặc có đơn, để chuyển qua lại và theo dõi đơn đặt trước
            "available_dates": self.orders.known_dates_from(today),
            "cutoff": self.config.cutoff_label(),
            "cutoff_passed": self.config.cutoff_passed_for(target_date),
            "summary": summary,
            "employees": [e.to_dict() for e in employees],
            "restaurants": [r.to_dict() for r in self.restaurants.list_serving_on(target_date)],
            "totals": self._totals(summary, employees),
            "status_counts": counts,
            "locked": self._is_locked(counts),
        }

    @staticmethod
    def _group_by_employee(rows) -> list:
        grouped = {}
        for row in rows:
            key = row["employee_email"]
            if key not in grouped:
                grouped[key] = EmployeeOrderSummary(row)
            grouped[key].add_line(row)
        return list(grouped.values())

    @staticmethod
    def _totals(summary, employees) -> dict:
        return {
            "grand_total": sum(e.total_cost for e in employees),
            "employee_count": len(employees),
            "item_count": sum(s["total_quantity"] for s in summary),
            "paid_count": sum(1 for e in employees if e.confirmed),
            "awaiting_count": sum(1 for e in employees if e.awaiting_confirmation),
            "collected_amount": sum(e.total_cost for e in employees if e.confirmed),
        }

    @staticmethod
    def _is_locked(counts: dict) -> bool:
        return any(counts.get(status) for status in OrderStatus.LOCKED)
