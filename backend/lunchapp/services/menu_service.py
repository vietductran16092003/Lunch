"""Nghiệp vụ thực đơn."""

from ..config import Config
from ..core.dates import Clock
from ..core.errors import NotFoundError, ValidationError
from ..models import MenuDay, MenuItem


class MenuService:

    def __init__(self, menu_repository, restaurant_repository, order_repository,
                 event_broker, config=Config):
        self.menu = menu_repository
        self.restaurants = restaurant_repository
        self.orders = order_repository
        self.events = event_broker
        self.config = config

    def get_menu(self, target_date=None) -> dict:
        target_date = Clock.date_or_today(target_date)
        items = self.menu.list_for_date(target_date)
        return {
            "date": target_date,
            "cutoff": self.config.cutoff_label(),
            # Giờ chốt chỉ áp cho hôm nay; ngày sau vẫn đặt trước được
            "cutoff_passed": self.config.cutoff_passed_for(target_date),
            "is_today": target_date == Clock.today(),
            "items": [i.to_dict() for i in items],
        }

    def available_dates(self, user_id) -> dict:
        """Những ngày đã có thực đơn, tính từ hôm nay trở đi.

        Nhân viên dùng danh sách này để chọn đặt hôm nay hay đặt trước hôm sau.
        """
        today = Clock.today()
        rows = self.menu.list_dates_from(today)
        ordered_dates = self.orders.ordered_dates_for_user(user_id, today)

        days = [
            MenuDay(
                date=r["date"],
                item_count=r["item_count"],
                is_today=r["date"] == today,
                closed=self.config.cutoff_passed_for(r["date"]),
                has_order=r["date"] in ordered_dates,
            )
            for r in rows
        ]

        # Mặc định mở ngày còn đặt được gần nhất; hôm nay chốt rồi thì nhảy sang hôm sau
        default_date = next((d.date for d in days if not d.closed), today)

        return {
            "today": today,
            "dates": [d.to_dict() for d in days],
            "default_date": default_date,
            "cutoff": self.config.cutoff_label(),
        }

    def create_item(self, data: dict) -> dict:
        name = (data.get("name") or "").strip()
        price = data.get("price")
        available_date = data.get("available_date")
        restaurant_id = data.get("restaurant_id")

        if not name or price is None or not available_date:
            raise ValidationError("Vui lòng nhập đủ tên món, giá, ngày áp dụng")

        # Yêu cầu nghiệp vụ: phải chọn nhà hàng trước khi thêm món
        if not restaurant_id:
            raise ValidationError("Vui lòng chọn nhà hàng trước khi thêm món")
        if self.restaurants.find_by_id(restaurant_id) is None:
            raise ValidationError("Nhà hàng không tồn tại")

        item = MenuItem(
            name=name,
            description=data.get("description") or "",
            price=price,
            available_date=available_date,
            restaurant_id=restaurant_id,
            image_url=(data.get("image_url") or "").strip() or None,
            tags=(data.get("tags") or "").strip() or None,
        )
        new_id = self.menu.create(item)

        self.events.publish(
            "menu_updated", {"id": new_id, "name": name, "date": available_date}
        )
        return {"id": new_id}

    def update_item(self, item_id, data: dict) -> dict:
        if self.menu.find_by_id(item_id) is None:
            raise NotFoundError("Không tìm thấy món ăn")

        item = MenuItem(
            name=data.get("name"),
            description=data.get("description"),
            price=data.get("price"),
            available_date=data.get("available_date"),
            restaurant_id=data.get("restaurant_id"),
            image_url=(data.get("image_url") or "").strip() or None,
            tags=(data.get("tags") or "").strip() or None,
        )
        self.menu.update(item_id, item)

        self.events.publish("menu_updated", {"id": item_id})
        return {"status": "updated"}

    def delete_item(self, item_id) -> dict:
        self.menu.delete(item_id)
        self.events.publish("menu_updated", {"id": item_id, "deleted": True})
        return {"status": "deleted"}
