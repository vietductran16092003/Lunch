"""Truy vấn bảng restaurants."""

from ..models import Restaurant
from .base import BaseRepository


class RestaurantRepository(BaseRepository):

    def list_all(self) -> list:
        return Restaurant.from_rows(
            self._fetch_all(
                "SELECT id, name, grab_url, external_id, address, rating, image_url "
                "FROM restaurants ORDER BY name"
            )
        )

    def find_by_id(self, restaurant_id) -> Restaurant | None:
        return Restaurant.from_row(
            self._fetch_one("SELECT * FROM restaurants WHERE id = ?", (restaurant_id,))
        )

    def create(self, restaurant: Restaurant) -> int:
        return self._insert(
            "INSERT INTO restaurants (name, grab_url, external_id, address, rating, image_url) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                restaurant.name, restaurant.grab_url, restaurant.external_id,
                restaurant.address, restaurant.rating, restaurant.image_url,
            ),
        )

    def delete(self, restaurant_id):
        self._execute("DELETE FROM restaurants WHERE id = ?", (restaurant_id,))

    def count_menu_items(self, restaurant_id) -> int:
        row = self._fetch_one(
            "SELECT COUNT(*) AS total FROM menu_items WHERE restaurant_id = ?", (restaurant_id,)
        )
        return row["total"] if row else 0

    def list_serving_on(self, target_date: str) -> list:
        """Nhà hàng có món trong thực đơn của một ngày."""
        return Restaurant.from_rows(
            self._fetch_all(
                """
                SELECT DISTINCT restaurants.id, restaurants.name, restaurants.grab_url
                FROM menu_items
                JOIN restaurants ON menu_items.restaurant_id = restaurants.id
                WHERE menu_items.available_date = ?
                """,
                (target_date,),
            )
        )

    def list_with_orders_on(self, target_date: str) -> list:
        """Nhà hàng thực sự có người đặt trong ngày và có link Grab để mở."""
        return Restaurant.from_rows(
            self._fetch_all(
                """
                SELECT DISTINCT restaurants.id, restaurants.name, restaurants.grab_url
                FROM order_items
                JOIN orders ON order_items.order_id = orders.id
                JOIN menu_items ON order_items.menu_item_id = menu_items.id
                JOIN restaurants ON menu_items.restaurant_id = restaurants.id
                WHERE orders.order_date = ? AND restaurants.grab_url IS NOT NULL
                """,
                (target_date,),
            )
        )
