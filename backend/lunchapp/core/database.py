"""Lớp quản lý kết nối và khởi tạo lược đồ SQLite."""

import sqlite3
from contextlib import contextmanager


class Database:
    """Đóng gói kết nối SQLite và việc dựng/nâng cấp lược đồ.

    Repository nhận một instance Database qua constructor, nên khi test chỉ cần
    truyền Database trỏ vào file tạm là xong.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def session(self, commit: bool = False):
        """Mở kết nối, tự đóng khi xong, tự rollback nếu có lỗi."""
        conn = self.connect()
        try:
            yield conn
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ===== Lược đồ =====

    @staticmethod
    def _columns(cursor, table) -> list:
        return [row["name"] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()]

    def _add_column_if_missing(self, cursor, table, column, ddl):
        if column not in self._columns(cursor, table):
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def init_schema(self):
        """Dựng bảng nếu chưa có và nâng cấp dần các bảng cũ. An toàn khi gọi lại."""
        with self.session(commit=True) as conn:
            cursor = conn.cursor()
            self._create_tables(cursor)
            self._migrate_columns(cursor)
            self._create_indexes(cursor)
            self._migrate_suppliers_to_restaurants(cursor)
            self._seed_demo_data(cursor)
            # Chạy sau cùng: cần users đã có (kể cả dữ liệu seed) mới suy được vai trò
            self._migrate_roles(cursor)

    def _create_tables(self, cursor):
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                phone TEXT,
                qr_image_url TEXT,
                google_sub TEXT,
                reset_token TEXT,
                reset_expires TEXT
            )
        """)

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

        # Một người có thể vừa điều phối vừa thủ quỹ, nên quan hệ là nhiều-nhiều
        # chứ không phải một cột role trên bảng users.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_roles (
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                PRIMARY KEY (user_id, role),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Lịch trực điều phối: mỗi ngày đúng một người, nên date làm khoá chính.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coordinator_schedule (
                date TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Cấu hình giờ chốt theo từng ngày. Bảng dựng sẵn ở đây để phần nghiệp vụ
        # deadline (mục 4.1) chỉ còn việc đọc/ghi, không phải đụng lại lược đồ.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deadline_config (
                date TEXT PRIMARY KEY,
                cutoff TEXT,
                auto_lock INTEGER DEFAULT 1,
                updated_at TEXT
            )
        """)

    def _migrate_columns(self, cursor):
        for column, ddl in [
            ("phone", "TEXT"), ("qr_image_url", "TEXT"), ("google_sub", "TEXT"),
            ("reset_token", "TEXT"), ("reset_expires", "TEXT"),
        ]:
            self._add_column_if_missing(cursor, "users", column, ddl)

        for column, ddl in [("restaurant_id", "INTEGER"), ("image_url", "TEXT")]:
            self._add_column_if_missing(cursor, "menu_items", column, ddl)

        for column, ddl in [
            ("payment_method", "TEXT DEFAULT 'cash'"), ("locked_at", "TEXT"),
            ("paid_at", "TEXT"), ("payment_confirmed_at", "TEXT"),
        ]:
            self._add_column_if_missing(cursor, "orders", column, ddl)

    def _create_indexes(self, cursor):
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_reset ON users (reset_token)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_date ON orders (order_date)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_menu_items_date ON menu_items (available_date)"
        )
        # Truy vấn hay gặp nhất là "vai trò của user X", nên đánh index theo user_id
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles (user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles (role)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_coordinator_schedule_user "
            "ON coordinator_schedule (user_id)"
        )

    def _migrate_roles(self, cursor):
        """Sinh dữ liệu user_roles lần đầu từ cột is_admin đang có.

        Chỉ chạy khi bảng còn rỗng, nên gọi init_schema nhiều lần cũng không ghi
        đè phân quyền mà quản trị viên đã chỉnh tay sau này. Cột is_admin được
        GIỮ NGUYÊN và vẫn được đồng bộ khi vai trò admin thay đổi, để phần code
        cũ còn đọc cột đó không vỡ.
        """
        from .roles import Role

        existing = cursor.execute("SELECT COUNT(*) FROM user_roles").fetchone()[0]
        if existing:
            return

        for row in cursor.execute("SELECT id, is_admin FROM users").fetchall():
            for role in Role.for_admin_flag(row["is_admin"]):
                cursor.execute(
                    "INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, ?)",
                    (row["id"], role),
                )

    def _migrate_suppliers_to_restaurants(self, cursor):
        """Chuyển dữ liệu bảng suppliers cũ sang restaurants rồi thôi dùng nó.

        Bảng suppliers giữ nguyên trên đĩa để không mất dữ liệu lịch sử, nhưng
        không còn chỗ nào trong ứng dụng đọc tới.
        """
        exists = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='suppliers'"
        ).fetchone()
        if not exists:
            return

        supplier_columns = self._columns(cursor, "suppliers")
        if "name" not in supplier_columns:
            return

        rating_expr = "rating" if "rating" in supplier_columns else "NULL"
        suppliers = cursor.execute(
            f"SELECT id, name, {rating_expr} AS rating FROM suppliers"
        ).fetchall()

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

        if "supplier_id" in self._columns(cursor, "menu_items"):
            orphans = cursor.execute(
                "SELECT id, supplier_id FROM menu_items "
                "WHERE restaurant_id IS NULL AND supplier_id IS NOT NULL"
            ).fetchall()
            for row in orphans:
                mapped = id_map.get(row["supplier_id"])
                if mapped:
                    cursor.execute(
                        "UPDATE menu_items SET restaurant_id = ? WHERE id = ?",
                        (mapped, row["id"]),
                    )

    def _seed_demo_data(self, cursor):
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
            from werkzeug.security import generate_password_hash

            for name, email, password, is_admin in [
                ("Admin", "admin@fpt.com", "admin123", 1),
                ("Nhân viên demo", "nhanvien@fpt.com", "123456", 0),
            ]:
                cursor.execute(
                    "INSERT INTO users (name, email, password, is_admin) VALUES (?, ?, ?, ?)",
                    (name, email, generate_password_hash(password), is_admin),
                )

        cursor.execute("SELECT COUNT(*) FROM menu_items")
        if cursor.fetchone()[0] == 0:
            from datetime import date

            today = date.today().isoformat()
            restaurant = cursor.execute(
                "SELECT id FROM restaurants ORDER BY id LIMIT 1"
            ).fetchone()
            restaurant_id = restaurant["id"] if restaurant else None
            for name, description, price in [
                ("Cơm sườn", "Cơm sườn nướng, canh, rau", 35000),
                ("Cơm gà", "Cơm gà xối mỡ, dưa leo", 35000),
                ("Bún bò", "Bún bò Huế, chả, giò", 40000),
            ]:
                cursor.execute(
                    "INSERT INTO menu_items "
                    "(name, description, price, available_date, restaurant_id) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (name, description, price, today, restaurant_id),
                )
