"""Truy vấn bảng menu_items."""

from ..models import MenuItem
from .base import BaseRepository

_SELECT_WITH_RESTAURANT = """
    SELECT menu_items.id, menu_items.name, menu_items.description,
           menu_items.price, menu_items.available_date, menu_items.image_url,
           menu_items.restaurant_id, menu_items.tags,
           restaurants.name AS restaurant_name,
           restaurants.rating AS restaurant_rating,
           restaurants.grab_url AS restaurant_grab_url
    FROM menu_items
    LEFT JOIN restaurants ON menu_items.restaurant_id = restaurants.id
"""


class MenuRepository(BaseRepository):

    def list_for_date(self, target_date: str) -> list:
        return MenuItem.from_rows(
            self._fetch_all(
                _SELECT_WITH_RESTAURANT
                + " WHERE menu_items.available_date = ? ORDER BY restaurants.name, menu_items.name",
                (target_date,),
            )
        )

    def find_by_id(self, item_id) -> MenuItem | None:
        return MenuItem.from_row(
            self._fetch_one("SELECT * FROM menu_items WHERE id = ?", (item_id,))
        )

    def list_dates_from(self, from_date: str) -> list:
        """Các ngày đã có thực đơn, kèm số món."""
        return self._fetch_all(
            """
            SELECT available_date AS date, COUNT(*) AS item_count
            FROM menu_items
            WHERE available_date >= ?
            GROUP BY available_date
            ORDER BY available_date
            """,
            (from_date,),
        )

    def filter_ids_on_date(self, item_ids: list, target_date: str) -> set:
        """Trong các id đưa vào, id nào thực sự thuộc thực đơn ngày đó."""
        if not item_ids:
            return set()
        placeholders = ",".join("?" * len(item_ids))
        rows = self._fetch_all(
            f"SELECT id FROM menu_items WHERE available_date = ? AND id IN ({placeholders})",
            (target_date, *item_ids),
        )
        return {r["id"] for r in rows}

    def find_matching(self, names: list, target_date: str) -> dict:
        """Khớp món theo TÊN sang thực đơn của một ngày khác (mã 3.3 - reorder).

        Mỗi ngày là một dòng `menu_items` riêng nên `menu_item_id` của đơn cũ
        không dùng lại được cho ngày mới; phải tìm món "cùng tên" đang bán vào
        `target_date`. Trả về dict {tên món (chuẩn hoá) -> MenuItem} để nơi gọi
        tự tra cứu, món trùng tên thì lấy dòng đầu tiên (theo restaurant/name).
        Tên được so khớp không phân biệt hoa/thường và bỏ khoảng trắng thừa vì
        đây chỉ là gợi ý tiện lợi, không phải khoá định danh.
        """
        if not names:
            return {}
        placeholders = ",".join("?" * len(names))
        rows = self._fetch_all(
            _SELECT_WITH_RESTAURANT
            + f" WHERE menu_items.available_date = ? "
              f"AND LOWER(TRIM(menu_items.name)) IN ({placeholders}) "
              "ORDER BY restaurants.name, menu_items.name",
            (target_date, *[str(n).strip().lower() for n in names]),
        )
        items = MenuItem.from_rows(rows)
        matched = {}
        for item in items:
            key = (item.name or "").strip().lower()
            # Trùng tên ở nhiều quán thì giữ lại kết quả đầu tiên tìm thấy
            matched.setdefault(key, item)
        return matched

    def create(self, item: MenuItem) -> int:
        return self._insert(
            "INSERT INTO menu_items "
            "(name, description, price, available_date, restaurant_id, image_url, tags) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                item.name, item.description, item.price,
                item.available_date, item.restaurant_id, item.image_url, item.tags,
            ),
        )

    def update(self, item_id, item: MenuItem):
        self._execute(
            """UPDATE menu_items
               SET name = ?, description = ?, price = ?, available_date = ?,
                   restaurant_id = ?, image_url = ?, tags = ?
               WHERE id = ?""",
            (
                item.name, item.description, item.price, item.available_date,
                item.restaurant_id, item.image_url, item.tags, item_id,
            ),
        )

    def delete(self, item_id):
        self._execute("DELETE FROM menu_items WHERE id = ?", (item_id,))

    def delete_for_date(self, target_date: str):
        """Xoá mọi món của một ngày — dùng khi gỡ bỏ hẳn ngày đó (OrderService.clear_date)."""
        self._execute("DELETE FROM menu_items WHERE available_date = ?", (target_date,))
