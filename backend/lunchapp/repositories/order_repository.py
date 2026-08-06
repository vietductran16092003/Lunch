"""Truy vấn bảng orders và order_items."""

from ..config import OrderStatus
from ..models import Order, OrderItem
from .base import BaseRepository

_ORDER_COLUMNS = (
    "id, user_id, order_date, status, payment_method, locked_at, paid_at, payment_confirmed_at"
)


class OrderRepository(BaseRepository):

    # ===== Đọc =====

    def find_by_id(self, order_id) -> Order | None:
        return Order.from_row(
            self._fetch_one(f"SELECT {_ORDER_COLUMNS} FROM orders WHERE id = ?", (order_id,))
        )

    def find_for_user_on(self, user_id, target_date: str) -> Order | None:
        return Order.from_row(
            self._fetch_one(
                f"SELECT {_ORDER_COLUMNS} FROM orders "
                "WHERE user_id = ? AND order_date = ? ORDER BY id DESC LIMIT 1",
                (user_id, target_date),
            )
        )

    def list_for_user(self, user_id) -> list:
        return Order.from_rows(
            self._fetch_all(
                f"SELECT {_ORDER_COLUMNS} FROM orders "
                "WHERE user_id = ? ORDER BY order_date DESC, id DESC",
                (user_id,),
            )
        )

    def load_items(self, order_id) -> list:
        return OrderItem.from_rows(
            self._fetch_all(
                """
                SELECT order_items.menu_item_id, order_items.quantity,
                       menu_items.name, menu_items.price, menu_items.image_url,
                       restaurants.name AS restaurant_name
                FROM order_items
                JOIN menu_items ON order_items.menu_item_id = menu_items.id
                LEFT JOIN restaurants ON menu_items.restaurant_id = restaurants.id
                WHERE order_items.order_id = ?
                ORDER BY menu_items.name
                """,
                (order_id,),
            )
        )

    def with_items(self, order: Order | None) -> Order | None:
        """Gắn danh sách món vào đơn."""
        if order is not None:
            order.items = self.load_items(order.id)
        return order

    def ordered_dates_for_user(self, user_id, from_date: str) -> set:
        rows = self._fetch_all(
            "SELECT DISTINCT order_date FROM orders WHERE user_id = ? AND order_date >= ?",
            (user_id, from_date),
        )
        return {r["order_date"] for r in rows}

    def known_dates_from(self, from_date: str) -> list:
        """Ngày có thực đơn hoặc có đơn, dùng cho bộ chọn ngày của quản trị viên."""
        rows = self._fetch_all(
            """
            SELECT DISTINCT available_date AS date FROM menu_items WHERE available_date >= ?
            UNION
            SELECT DISTINCT order_date AS date FROM orders WHERE order_date >= ?
            ORDER BY date
            """,
            (from_date, from_date),
        )
        return [r["date"] for r in rows]

    # ===== Ghi =====

    def create(self, user_id, target_date: str, payment_method: str = "transfer") -> int:
        return self._insert(
            "INSERT INTO orders (user_id, order_date, status, payment_method) "
            "VALUES (?, ?, ?, ?)",
            (user_id, target_date, OrderStatus.PENDING, payment_method),
        )

    def replace_items(self, order_id, items: list):
        """Xóa hết dòng cũ rồi ghi lại — đơn giản và luôn khớp với ý người dùng."""
        with self.db.session(commit=True) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
            for item in items:
                quantity = item.get("quantity", 0)
                if quantity and quantity > 0:
                    cursor.execute(
                        "INSERT INTO order_items (order_id, menu_item_id, quantity) "
                        "VALUES (?, ?, ?)",
                        (order_id, item.get("menu_item_id"), quantity),
                    )

    def set_payment_method(self, order_id, payment_method: str):
        self._execute(
            "UPDATE orders SET payment_method = ? WHERE id = ?", (payment_method, order_id)
        )

    def delete(self, order_id):
        with self.db.session(commit=True) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
            cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))

    def mark_paid(self, order_id, paid_at: str):
        self._execute("UPDATE orders SET paid_at = ? WHERE id = ?", (paid_at, order_id))

    def confirm_payment(self, order_id, paid_at: str, confirmed_at: str):
        self._execute(
            "UPDATE orders SET status = ?, paid_at = ?, payment_confirmed_at = ? WHERE id = ?",
            (OrderStatus.COMPLETED, paid_at, confirmed_at, order_id),
        )

    def lock_pending_on(self, target_date: str, locked_at: str) -> int:
        return self._execute(
            "UPDATE orders SET status = ?, locked_at = ? WHERE order_date = ? AND status = ?",
            (OrderStatus.CLOSED, locked_at, target_date, OrderStatus.PENDING),
        )

    def mark_ordered_on(self, target_date: str) -> int:
        return self._execute(
            "UPDATE orders SET status = ? WHERE order_date = ? AND status = ?",
            (OrderStatus.ORDERED, target_date, OrderStatus.CLOSED),
        )

    # ===== Tổng hợp cho bảng điều khiển =====

    def summary_by_item(self, target_date: str) -> list:
        return self._fetch_all(
            """
            SELECT menu_items.id AS menu_item_id,
                   menu_items.name AS item_name,
                   menu_items.price AS price,
                   restaurants.name AS restaurant_name,
                   restaurants.grab_url AS restaurant_grab_url,
                   SUM(order_items.quantity) AS total_quantity
            FROM order_items
            JOIN orders ON order_items.order_id = orders.id
            JOIN menu_items ON order_items.menu_item_id = menu_items.id
            LEFT JOIN restaurants ON menu_items.restaurant_id = restaurants.id
            WHERE orders.order_date = ?
            GROUP BY menu_items.id
            ORDER BY restaurants.name, menu_items.name
            """,
            (target_date,),
        )

    def rows_by_employee(self, target_date: str) -> list:
        return self._fetch_all(
            """
            SELECT users.id AS employee_id,
                   users.name AS employee_name,
                   users.email AS employee_email,
                   menu_items.name AS item_name,
                   menu_items.price AS price,
                   order_items.quantity AS quantity,
                   orders.id AS order_id,
                   orders.status AS status,
                   orders.payment_method AS payment_method,
                   orders.paid_at AS paid_at,
                   orders.payment_confirmed_at AS payment_confirmed_at
            FROM order_items
            JOIN orders ON order_items.order_id = orders.id
            JOIN users ON orders.user_id = users.id
            JOIN menu_items ON order_items.menu_item_id = menu_items.id
            WHERE orders.order_date = ?
            ORDER BY users.name, menu_items.name
            """,
            (target_date,),
        )

    def status_counts(self, target_date: str) -> dict:
        rows = self._fetch_all(
            "SELECT status, COUNT(*) AS total FROM orders WHERE order_date = ? GROUP BY status",
            (target_date,),
        )
        return {r["status"]: r["total"] for r in rows}

    def export_rows(self, target_date: str) -> list:
        return self._fetch_all(
            """
            SELECT users.name AS employee_name,
                   restaurants.name AS restaurant_name,
                   menu_items.name AS item_name,
                   menu_items.price AS price,
                   order_items.quantity AS quantity,
                   orders.status AS status,
                   orders.payment_method AS payment_method,
                   orders.paid_at AS paid_at,
                   orders.payment_confirmed_at AS payment_confirmed_at
            FROM order_items
            JOIN orders ON order_items.order_id = orders.id
            JOIN users ON orders.user_id = users.id
            JOIN menu_items ON order_items.menu_item_id = menu_items.id
            LEFT JOIN restaurants ON menu_items.restaurant_id = restaurants.id
            WHERE orders.order_date = ?
            ORDER BY users.name, menu_items.name
            """,
            (target_date,),
        )
