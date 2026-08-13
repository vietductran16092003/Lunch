"""Thực thể một món trong danh mục gốc của một nhà hàng (dùng lại nhiều ngày)."""

from .base import BaseModel


class CatalogItem(BaseModel):
    FIELDS = ("id", "restaurant_id", "name", "description", "price", "tags", "created_at")

    def __init__(self, id=None, restaurant_id=None, name=None, description=None,
                 price=0, tags=None, created_at=None):
        self.id = id
        self.restaurant_id = restaurant_id
        self.name = name
        self.description = description
        self.price = price
        self.tags = tags
        self.created_at = created_at

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        return cls(
            id=cls.column(row, "id"),
            restaurant_id=cls.column(row, "restaurant_id"),
            name=cls.column(row, "name"),
            description=cls.column(row, "description"),
            price=cls.column(row, "price", 0),
            tags=cls.column(row, "tags"),
            created_at=cls.column(row, "created_at"),
        )
