"""Truy vấn bảng restaurant_menu_catalog."""

from ..models import CatalogItem
from .base import BaseRepository


class CatalogRepository(BaseRepository):
    """CRUD cho danh mục món gốc của nhà hàng — dùng lại nhiều ngày, không gắn với ngày cụ thể nào."""

    def list_for_restaurant(self, restaurant_id) -> list:
        rows = self._fetch_all(
            "SELECT * FROM restaurant_menu_catalog WHERE restaurant_id = ? ORDER BY name",
            (restaurant_id,),
        )
        return CatalogItem.from_rows(rows)

    def find_by_id(self, catalog_id) -> CatalogItem | None:
        return CatalogItem.from_row(
            self._fetch_one("SELECT * FROM restaurant_menu_catalog WHERE id = ?", (catalog_id,))
        )

    def find_many(self, catalog_ids: list) -> list:
        """Nhiều món cùng lúc theo danh sách id — dùng khi áp dụng hàng loạt món đã tick vào thực đơn."""
        if not catalog_ids:
            return []
        placeholders = ",".join("?" * len(catalog_ids))
        rows = self._fetch_all(
            f"SELECT * FROM restaurant_menu_catalog WHERE id IN ({placeholders})",
            tuple(catalog_ids),
        )
        return CatalogItem.from_rows(rows)

    def create(self, item: CatalogItem) -> int:
        return self._insert(
            "INSERT INTO restaurant_menu_catalog (restaurant_id, name, description, price, tags) "
            "VALUES (?, ?, ?, ?, ?)",
            (item.restaurant_id, item.name, item.description, item.price, item.tags),
        )

    def delete(self, catalog_id):
        self._execute("DELETE FROM restaurant_menu_catalog WHERE id = ?", (catalog_id,))
