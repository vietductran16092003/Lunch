import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "lunch.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _columns(cursor, table):
    return [row["name"] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()]


def _add_column_if_missing(cursor, table, column, ddl):
    if column not in _columns(cursor, table):
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            phone TEXT,
            qr_image_url TEXT
        )
    """)
    _add_column_if_missing(cursor, "users", "phone", "TEXT")
    _add_column_if_missing(cursor, "users", "qr_image_url", "TEXT")
    _add_column_if_missing(cursor, "users", "google_sub", "TEXT")
    _add_column_if_missing(cursor, "users", "reset_token", "TEXT")
    _add_column_if_missing(cursor, "users", "reset_expires", "TEXT")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_reset ON users (reset_token)")

    # Nhà hàng lấy từ GrabFood — thay hoàn toàn cho khái niệm "nhà cung cấp" cũ
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS restaurants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            grab_url TEXT,
            external_id TEXT,
            address TEXT,
            rating REAL,
            image_url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            available_date TEXT NOT NULL,
            restaurant_id INTEGER,
            image_url TEXT,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants (id)
        )
    """)
    _add_column_if_missing(cursor, "menu_items", "restaurant_id", "INTEGER")
    _add_column_if_missing(cursor, "menu_items", "image_url", "TEXT")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            payment_method TEXT DEFAULT 'cash',
            locked_at TEXT,
            paid_at TEXT,
            payment_confirmed_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    _add_column_if_missing(cursor, "orders", "payment_method", "TEXT DEFAULT 'cash'")
    _add_column_if_missing(cursor, "orders", "locked_at", "TEXT")
    _add_column_if_missing(cursor, "orders", "paid_at", "TEXT")
    _add_column_if_missing(cursor, "orders", "payment_confirmed_at", "TEXT")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            menu_item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (menu_item_id) REFERENCES menu_items (id)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_date ON orders (order_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_menu_items_date ON menu_items (available_date)")

    _migrate_suppliers_to_restaurants(cursor)
    _seed_demo_data(cursor)

    conn.commit()
    conn.close()


def _migrate_suppliers_to_restaurants(cursor):
    """Chuyển dữ liệu từ bảng suppliers cũ sang restaurants rồi thôi dùng nó.

    Bảng suppliers được giữ nguyên trên đĩa để không mất dữ liệu lịch sử, nhưng
    không còn chỗ nào trong ứng dụng đọc tới nữa.
    """
    has_suppliers = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='suppliers'"
    ).fetchone()
    if not has_suppliers:
        return

    supplier_columns = _columns(cursor, "suppliers")
    if "name" not in supplier_columns:
        return

    rating_expr = "rating" if "rating" in supplier_columns else "NULL"
    suppliers = cursor.execute(f"SELECT id, name, {rating_expr} AS rating FROM suppliers").fetchall()

    id_map = {}
    for supplier in suppliers:
        existing = cursor.execute(
            "SELECT id FROM restaurants WHERE name = ?", (supplier["name"],)
        ).fetchone()
        if existing:
            id_map[supplier["id"]] = existing["id"]
            continue
        cursor.execute(
            "INSERT INTO restaurants (name, rating) VALUES (?, ?)",
            (supplier["name"], supplier["rating"]),
        )
        id_map[supplier["id"]] = cursor.lastrowid

    # Nối lại các món ăn cũ đang trỏ vào supplier_id
    if "supplier_id" in _columns(cursor, "menu_items"):
        orphans = cursor.execute(
            "SELECT id, supplier_id FROM menu_items WHERE restaurant_id IS NULL AND supplier_id IS NOT NULL"
        ).fetchall()
        for row in orphans:
            mapped = id_map.get(row["supplier_id"])
            if mapped:
                cursor.execute(
                    "UPDATE menu_items SET restaurant_id = ? WHERE id = ?", (mapped, row["id"])
                )


def _seed_demo_data(cursor):
    cursor.execute("SELECT COUNT(*) FROM restaurants")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO restaurants (name, grab_url, rating, address) VALUES (?, ?, ?, ?)",
            (
                "Quán cơm ABC",
                "https://food.grab.com/vn/vi/restaurant/quan-com-abc",
                4.6,
                "12 Nguyễn Trãi, Thanh Xuân, Hà Nội",
            ),
        )

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        from auth import hash_password

        for name, email, password, is_admin in [
            ("Admin", "admin@fpt.com", "admin123", 1),
            ("Nhân viên demo", "nhanvien@fpt.com", "123456", 0),
        ]:
            cursor.execute(
                "INSERT INTO users (name, email, password, is_admin) VALUES (?, ?, ?, ?)",
                (name, email, hash_password(password), is_admin),
            )

    cursor.execute("SELECT COUNT(*) FROM menu_items")
    if cursor.fetchone()[0] == 0:
        from datetime import date

        today = date.today().isoformat()
        restaurant = cursor.execute("SELECT id FROM restaurants ORDER BY id LIMIT 1").fetchone()
        restaurant_id = restaurant["id"] if restaurant else None
        for name, description, price in [
            ("Cơm sườn", "Cơm sườn nướng, canh, rau", 35000),
            ("Cơm gà", "Cơm gà xối mỡ, dưa leo", 35000),
            ("Bún bò", "Bún bò Huế, chả, giò", 40000),
        ]:
            cursor.execute(
                "INSERT INTO menu_items (name, description, price, available_date, restaurant_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, description, price, today, restaurant_id),
            )


if __name__ == "__main__":
    init_db()
    print("Đã khởi tạo database và bảng dữ liệu mẫu.")
