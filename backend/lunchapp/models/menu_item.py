"""Thực thể món ăn trong thực đơn một ngày."""

from .base import BaseModel


class MenuItem(BaseModel):
    FIELDS = (
        "id", "name", "description", "price", "available_date",
        "restaurant_id", "image_url",
    )

    def __init__(self, id=None, name=None, description=None, price=0, available_date=None,
                 restaurant_id=None, image_url=None,
                 restaurant_name=None, restaurant_rating=None, restaurant_grab_url=None):
        self.id = id
        self.name = name
        self.description = description
        self.price = price
        self.available_date = available_date
        self.restaurant_id = restaurant_id
        self.image_url = image_url
        # Các trường lấy kèm từ JOIN nhà hàng, chỉ để hiển thị
        self.restaurant_name = restaurant_name
        self.restaurant_rating = restaurant_rating
        self.restaurant_grab_url = restaurant_grab_url

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        return cls(
            id=cls.column(row, "id"),
            name=cls.column(row, "name"),
            description=cls.column(row, "description"),
            price=cls.column(row, "price", 0),
            available_date=cls.column(row, "available_date"),
            restaurant_id=cls.column(row, "restaurant_id"),
            image_url=cls.column(row, "image_url"),
            restaurant_name=cls.column(row, "restaurant_name"),
            restaurant_rating=cls.column(row, "restaurant_rating"),
            restaurant_grab_url=cls.column(row, "restaurant_grab_url"),
        )

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "restaurant_name": self.restaurant_name,
            "restaurant_rating": self.restaurant_rating,
            "restaurant_grab_url": self.restaurant_grab_url,
        })
        return data


class MenuDay:
    """Một ngày có thực đơn, kèm trạng thái còn đặt được hay không."""

    def __init__(self, date, item_count, is_today, closed, has_order=False):
        self.date = date
        self.item_count = item_count
        self.is_today = is_today
        self.closed = closed
        self.has_order = has_order

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "item_count": self.item_count,
            "is_today": self.is_today,
            "closed": self.closed,
            "has_order": self.has_order,
        }
