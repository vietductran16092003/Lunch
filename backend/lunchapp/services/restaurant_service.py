"""Nghiệp vụ quản lý nhà hàng."""

from ..core.errors import NotFoundError, ValidationError
from ..models import Restaurant


class RestaurantService:

    def __init__(self, restaurant_repository, grab_service, event_broker):
        self.restaurants = restaurant_repository
        self.grab = grab_service
        self.events = event_broker

    def list_all(self) -> list:
        return [r.to_dict() for r in self.restaurants.list_all()]

    def preview_from_url(self, grab_url: str) -> dict:
        """Đọc thông tin từ đường dẫn để quản trị viên xem trước, chưa ghi database."""
        info = self.grab.parse_restaurant_url(grab_url)
        fetched = info["source"] == "fetch"
        return {
            "restaurant": info,
            "fetched": fetched,
            "hint": None if fetched else
            "Đã đọc tên từ đường dẫn — vui lòng kiểm tra và sửa lại cho đúng trước khi lưu.",
        }

    def create(self, data: dict) -> dict:
        name = (data.get("name") or "").strip()
        grab_url = (data.get("grab_url") or "").strip()

        if not name:
            raise ValidationError("Vui lòng nhập tên nhà hàng")
        if grab_url and not self.grab.is_grab_url(grab_url):
            raise ValidationError("Đường dẫn phải thuộc food.grab.com")

        restaurant = Restaurant(
            name=name,
            grab_url=grab_url or None,
            external_id=(data.get("external_id") or "").strip() or None,
            address=(data.get("address") or "").strip() or None,
            rating=self._parse_rating(data.get("rating")),
            image_url=(data.get("image_url") or "").strip() or None,
        )

        new_id = self.restaurants.create(restaurant)
        self.events.publish("restaurant_added", {"id": new_id, "name": name})
        return {"id": new_id, "name": name}

    def update(self, restaurant_id, data: dict) -> dict:
        """Sửa thông tin nhà hàng (mã 2.5).

        Chỉ ghi đè những trường được gửi lên, trường vắng mặt giữ nguyên giá trị
        cũ — nhờ vậy giao diện sửa từng phần không vô tình xoá dữ liệu.
        """
        existing = self.restaurants.find_by_id(restaurant_id)
        if existing is None:
            raise NotFoundError("Không tìm thấy nhà hàng")

        if "name" in data:
            name = (data.get("name") or "").strip()
            if not name:
                raise ValidationError("Vui lòng nhập tên nhà hàng")
            existing.name = name

        if "grab_url" in data:
            grab_url = (data.get("grab_url") or "").strip()
            if grab_url and not self.grab.is_grab_url(grab_url):
                raise ValidationError("Đường dẫn phải thuộc food.grab.com")
            existing.grab_url = grab_url or None

        if "address" in data:
            existing.address = (data.get("address") or "").strip() or None
        if "image_url" in data:
            existing.image_url = (data.get("image_url") or "").strip() or None
        if "external_id" in data:
            existing.external_id = (data.get("external_id") or "").strip() or None
        if "rating" in data:
            existing.rating = self._parse_rating(data.get("rating"))

        self.restaurants.update(existing)
        self.events.publish("restaurant_updated", {
            "id": existing.id, "name": existing.name
        })
        return existing.to_dict()

    def delete(self, restaurant_id):
        in_use = self.restaurants.count_menu_items(restaurant_id)
        if in_use:
            raise ValidationError(
                f"Nhà hàng đang có {in_use} món trong thực đơn, hãy xóa món trước"
            )
        self.restaurants.delete(restaurant_id)

    @staticmethod
    def _parse_rating(value):
        try:
            return float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None
