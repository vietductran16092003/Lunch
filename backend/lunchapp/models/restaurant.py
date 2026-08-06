"""Thực thể nhà hàng (nguồn GrabFood)."""

from .base import BaseModel


class Restaurant(BaseModel):
    FIELDS = ("id", "name", "grab_url", "external_id", "address", "rating", "image_url")

    def __init__(self, id=None, name=None, grab_url=None, external_id=None,
                 address=None, rating=None, image_url=None):
        self.id = id
        self.name = name
        self.grab_url = grab_url
        self.external_id = external_id
        self.address = address
        self.rating = rating
        self.image_url = image_url

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        return cls(
            id=cls.column(row, "id"),
            name=cls.column(row, "name"),
            grab_url=cls.column(row, "grab_url"),
            external_id=cls.column(row, "external_id"),
            address=cls.column(row, "address"),
            rating=cls.column(row, "rating"),
            image_url=cls.column(row, "image_url"),
        )

    def has_grab_link(self) -> bool:
        return bool(self.grab_url)

    def to_grab_link(self) -> dict:
        return {"id": self.id, "name": self.name, "grab_url": self.grab_url}
