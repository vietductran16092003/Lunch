"""Tổng hợp dữ liệu cho bảng điều khiển của người đứng ra đặt."""

from ..config import Config, OrderStatus
from ..core.dates import Clock


class EmployeeOrderSummary:
    """Gộp nhiều dòng món của cùng một nhân viên thành một bản ghi."""

    def __init__(self, row):
        """Khởi tạo từ dòng đầu tiên của nhân viên này; add_line() gộp thêm các món sau."""
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

    def __init__(self, order_repository, restaurant_repository, config=Config,
                 order_owner_repository=None):
        self.orders = order_repository
        self.restaurants = restaurant_repository
        self.config = config
        self.order_owners = order_owner_repository

    def build(self, target_date=None) -> dict:
        """Toàn bộ dữ liệu Bảng điều khiển cho một ngày: tổng hợp theo món, chi
        tiết theo nhân viên, và danh sách ngày khác đang có dữ liệu."""
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
            "available_dates": self._available_dates(today),
            "cutoff": self.config.cutoff_label(),
            "cutoff_passed": self.config.cutoff_passed_for(target_date),
            "summary": summary,
            "employees": [e.to_dict() for e in employees],
            "restaurants": [r.to_dict() for r in self.restaurants.list_serving_on(target_date)],
            "totals": self._totals(summary, employees),
            "status_counts": counts,
            "locked": self._is_locked(counts),
        }

    def grouped_by_restaurant(self, target_date=None) -> dict:
        """Gộp toàn bộ đơn một ngày theo quán, cho coordinator copy tay vào Grab (mã 4.2).

        Khác với build() (nhìn phẳng theo món): ở đây phải trả về dạng cây
        quán -> món, kèm ghi chú (mã 3.5) gộp từ mọi đơn để coordinator biết
        cần dặn quán thêm gì. Duyệt bằng Python thuần cho dễ đọc, quy mô app
        này không cần SQL JOIN phức tạp.
        """
        target_date = Clock.date_or_today(target_date)
        orders = self.orders.list_for_date(target_date)

        # restaurant_name -> {"items": {item_name: {...}}, "grab_url": ...}
        restaurants = {}
        for order in orders:
            for item in order.items:
                rname = item.restaurant_name or "Không rõ quán"
                bucket = restaurants.setdefault(rname, {"items": {}, "grab_url": None})
                entry = bucket["items"].setdefault(
                    item.name, {"name": item.name, "price": item.price,
                                "total_quantity": 0, "notes": []}
                )
                entry["total_quantity"] += item.quantity
                note = (item.note or "").strip()
                if note and note not in entry["notes"]:
                    entry["notes"].append(note)

        # Lấy id/grab_url theo tên quán từ bảng restaurants (đủ dùng ở quy mô hiện tại)
        all_restaurants = {r.name: r for r in self.restaurants.list_all()}

        result = []
        grand_total = 0
        for rname, bucket in sorted(restaurants.items()):
            items = sorted(bucket["items"].values(), key=lambda i: i["name"])
            subtotal = sum(i["price"] * i["total_quantity"] for i in items)
            grand_total += subtotal
            match = all_restaurants.get(rname)
            result.append({
                "restaurant_id": match.id if match else None,
                "restaurant_name": rname,
                "grab_url": match.grab_url if match else None,
                "items": items,
                "subtotal": subtotal,
            })

        return {"date": target_date, "restaurants": result, "grand_total": grand_total}

    def _available_dates(self, from_date: str) -> list:
        """Danh sách ngày (từ from_date trở đi) đã có thực đơn/đơn, kèm ai đang
        phụ trách mỗi ngày — dùng để vẽ dải chọn ngày + dấu x gỡ ngày ở frontend."""
        owners = {}
        if self.order_owners:
            owners = {row["order_date"]: row["user_id"] for row in self.order_owners.list_from(from_date)}
        return [
            {"date": d, "owner_id": owners.get(d)}
            for d in self.orders.known_dates_from(from_date)
        ]

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
