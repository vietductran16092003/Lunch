"""Nghiệp vụ thực đơn."""

from ..config import Config
from ..core.dates import Clock
from ..core.errors import NotFoundError, ValidationError
from ..models import CatalogItem, MenuDay, MenuItem


class MenuService:
    """Thực đơn theo ngày + danh mục món gốc dùng lại nhiều ngày. Các thao tác
    ghi (create/update/delete/apply_catalog_items) đi qua CollectorService để
    kiểm/chiếm quyền phụ trách ngày đó, nếu collector_service được truyền vào."""

    def __init__(self, menu_repository, restaurant_repository, order_repository,
                 event_broker, config=Config, catalog_repository=None, collector_service=None):
        self.menu = menu_repository
        self.restaurants = restaurant_repository
        self.orders = order_repository
        self.events = event_broker
        self.config = config
        self.catalog = catalog_repository
        self.collectors = collector_service

    def get_menu(self, target_date=None) -> dict:
        """Danh sách món của một ngày, kèm trạng thái giờ chốt."""
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

        # Mặc định mở ngày còn đặt được gần nhất; hôm nay chốt rồi thì nhảy sang hôm sau.
        # Chỉ xét trong các ngày ĐÃ có thực đơn — dùng cho nhân viên chọn ngày để đặt.
        default_date = next((d.date for d in days if not d.closed), today)

        return {
            "today": today,
            "dates": [d.to_dict() for d in days],
            "default_date": default_date,
            # Vòng đặt đang mở theo giờ chốt, KHÔNG phụ thuộc đã có thực đơn hay
            # chưa — dùng cho các khoá theo "vòng hiện tại" (broadcast/thông tin
            # nhận tiền ở trang Đặt hàng), phải khớp Config.current_order_date()
            # mà backend dùng để authorize, nếu không frontend/backend sẽ lệch nhau.
            "current_round_date": self.config.current_order_date(),
            "cutoff": self.config.cutoff_label(),
        }

    def _assert_single_restaurant(self, available_date, restaurant_id, exclude_item_id=None):
        """Mỗi ngày chỉ đặt được 1 quán — chặn ngay khi thêm/sửa món khác quán
        cho cùng một ngày đã có món của quán khác."""
        existing = [
            i for i in self.menu.list_for_date(available_date) if i.id != exclude_item_id
        ]
        conflict = next((i for i in existing if i.restaurant_id != restaurant_id), None)
        if conflict:
            raise ValidationError(
                f'Ngày {available_date} đã có món của quán "{conflict.restaurant_name}" — '
                "mỗi ngày chỉ đặt được 1 quán. Xoá hết món cũ trước khi đổi quán."
            )

    def create_item(self, data: dict, actor_id=None, is_admin=False) -> dict:
        """Thêm 1 món cho một ngày cụ thể — người thêm món đầu tiên của ngày
        đó tự thành người phụ trách (xem CollectorService.authorize_and_claim)."""
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
        self._assert_single_restaurant(available_date, restaurant_id)
        if self.collectors:
            self.collectors.authorize_and_claim(actor_id, is_admin, available_date)

        item = MenuItem(
            name=name,
            description=data.get("description") or "",
            price=price,
            available_date=available_date,
            restaurant_id=restaurant_id,
            tags=(data.get("tags") or "").strip() or None,
        )
        new_id = self.menu.create(item)

        self.events.publish(
            "menu_updated", {"id": new_id, "name": name, "date": available_date}
        )
        return {"id": new_id}

    def update_item(self, item_id, data: dict, actor_id=None, is_admin=False) -> dict:
        """Sửa một món — chỉ admin hoặc người đang phụ trách ngày của món đó
        (cả ngày cũ lẫn ngày mới nếu đổi ngày) mới sửa được."""
        existing = self.menu.find_by_id(item_id)
        if existing is None:
            raise NotFoundError("Không tìm thấy món ăn")

        # Thiếu trong payload thì giữ nguyên giá trị cũ — payload thiếu trường
        # không được phép âm thầm xoá mất ngày/quán đang gán cho món.
        available_date = data.get("available_date") or existing.available_date
        restaurant_id = data.get("restaurant_id") or existing.restaurant_id

        # Chỉ kiểm bất biến khi THỰC SỰ đổi ngày/quán — nếu chỉ sửa tên/giá thì
        # dù ngày đó lỡ có dữ liệu cũ vi phạm (từ trước khi có ràng buộc này),
        # món đang sửa không phải nguyên nhân nên không chặn oan.
        if available_date != existing.available_date or restaurant_id != existing.restaurant_id:
            self._assert_single_restaurant(available_date, restaurant_id, exclude_item_id=item_id)
        if self.collectors:
            self.collectors.authorize(actor_id, is_admin, existing.available_date)
            if available_date != existing.available_date:
                self.collectors.authorize(actor_id, is_admin, available_date)

        item = MenuItem(
            name=data.get("name", existing.name),
            description=data.get("description", existing.description),
            price=data.get("price", existing.price),
            available_date=available_date,
            restaurant_id=restaurant_id,
            tags=(data.get("tags") if "tags" in data else existing.tags) or None,
        )
        self.menu.update(item_id, item)

        self.events.publish("menu_updated", {"id": item_id})
        return {"status": "updated"}

    def delete_item(self, item_id, actor_id=None, is_admin=False) -> dict:
        """Xoá một món — chỉ admin hoặc người đang phụ trách ngày của món đó."""
        existing = self.menu.find_by_id(item_id)
        if existing is None:
            raise NotFoundError("Không tìm thấy món ăn")
        if self.collectors:
            self.collectors.authorize(actor_id, is_admin, existing.available_date)

        self.menu.delete(item_id)
        self.events.publish("menu_updated", {"id": item_id, "deleted": True})
        return {"status": "deleted"}

    # ===== Danh mục món gốc của nhà hàng (dùng lại nhiều ngày) =====

    def list_catalog(self, restaurant_id) -> dict:
        """Danh mục món gốc của một nhà hàng — dùng để tick chọn khi áp dụng thực đơn cho một ngày."""
        if self.restaurants.find_by_id(restaurant_id) is None:
            raise NotFoundError("Nhà hàng không tồn tại")
        return {"items": [i.to_dict() for i in self.catalog.list_for_restaurant(restaurant_id)]}

    def add_catalog_item(self, restaurant_id, data: dict) -> dict:
        """Thêm 1 món vào danh mục gốc của nhà hàng — chưa gán ngày nào cả, chỉ có ý nghĩa để tick áp dụng sau."""
        name = (data.get("name") or "").strip()
        price = data.get("price")
        if self.restaurants.find_by_id(restaurant_id) is None:
            raise NotFoundError("Nhà hàng không tồn tại")
        if not name or price is None:
            raise ValidationError("Vui lòng nhập tên món và giá")

        item = CatalogItem(
            restaurant_id=restaurant_id,
            name=name,
            description=(data.get("description") or "").strip() or None,
            price=price,
            tags=(data.get("tags") or "").strip() or None,
        )
        new_id = self.catalog.create(item)
        return {"id": new_id}

    def delete_catalog_item(self, catalog_id) -> dict:
        """Xoá món khỏi danh mục gốc — không ảnh hưởng các ngày đã áp dụng món này trước đó (dữ liệu đã copy)."""
        self.catalog.delete(catalog_id)
        return {"status": "deleted"}

    def apply_catalog_items(self, available_date, restaurant_id, catalog_ids: list,
                             actor_id=None, is_admin=False) -> dict:
        """Thêm hàng loạt món từ danh mục gốc của nhà hàng vào thực đơn một
        ngày — copy dữ liệu, không tham chiếu, để sau này sửa giá gốc trong
        danh mục không ảnh hưởng ngược các ngày đã áp dụng."""
        if not available_date:
            raise ValidationError("Vui lòng chọn ngày áp dụng")
        if self.restaurants.find_by_id(restaurant_id) is None:
            raise ValidationError("Nhà hàng không tồn tại")
        if not catalog_ids:
            raise ValidationError("Vui lòng chọn ít nhất một món")
        self._assert_single_restaurant(available_date, restaurant_id)
        if self.collectors:
            self.collectors.authorize_and_claim(actor_id, is_admin, available_date)

        catalog_items = self.catalog.find_many(catalog_ids)
        found_ids = {i.id for i in catalog_items}
        missing = set(catalog_ids) - found_ids
        if missing:
            raise ValidationError("Một số món trong danh mục không còn tồn tại")

        # Món đã áp dụng cho ngày này rồi thì bỏ qua, tránh trùng khi bấm lại
        existing_names = {
            i.name.strip().lower() for i in self.menu.list_for_date(available_date)
        }

        created_ids = []
        skipped = []
        for catalog_item in catalog_items:
            if catalog_item.name.strip().lower() in existing_names:
                skipped.append(catalog_item.name)
                continue
            item = MenuItem(
                name=catalog_item.name,
                description=catalog_item.description,
                price=catalog_item.price,
                available_date=available_date,
                restaurant_id=restaurant_id,
                tags=catalog_item.tags,
            )
            created_ids.append(self.menu.create(item))

        if created_ids:
            self.events.publish(
                "menu_updated", {"date": available_date, "count": len(created_ids)}
            )
        return {"created": len(created_ids), "skipped": skipped}
