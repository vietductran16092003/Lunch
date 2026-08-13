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
        """Tên các cột hiện có của một bảng — dùng để biết cột nào còn thiếu."""
        return [row["name"] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()]

    def _add_column_if_missing(self, cursor, table, column, ddl):
        """Thêm cột nếu chưa có — cách nâng cấp bảng cũ không cần công cụ migration riêng."""
        if column not in self._columns(cursor, table):
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def init_schema(self):
        """Dựng bảng nếu chưa có và nâng cấp dần các bảng cũ. An toàn khi gọi lại."""
        with self.session(commit=True) as conn:
            cursor = conn.cursor()
            self._create_tables(cursor)
            self._migrate_columns(cursor)
            self._create_indexes(cursor)
            self._create_constraints(cursor)
            self._migrate_suppliers_to_restaurants(cursor)
            self._seed_demo_data(cursor)
            self._seed_fund(cursor)
            self._seed_default_team(cursor)
            # Chạy sau cùng: cần users đã có (kể cả dữ liệu seed) mới suy được vai trò
            self._migrate_roles(cursor)

    def _create_tables(self, cursor):
        """Dựng mọi bảng nếu chưa có — idempotent (CREATE TABLE IF NOT EXISTS), an toàn gọi lại mỗi lần app khởi động."""
        # Chuẩn bị sẵn cho sau này (nếu có nhiều văn phòng/nhóm cùng dùng chung
        # app) — CHỈ thêm cột, CHƯA lọc dữ liệu theo team_id ở bất kỳ đâu.
        # Hiện tại cả app coi như 1 team duy nhất (id=1); xem _seed_default_team().
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

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

        # Người đứng ra đặt của một ngày — không cố định ở tài khoản admin nữa.
        # Ai thêm món đầu tiên cho ngày đó thì tự nhận, admin luôn được can
        # thiệp bất kể ai đang giữ ngày đó (không kiểm tra qua bảng này).
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_owners (
                order_date TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                set_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Danh mục món "gốc" của một nhà hàng — nhập một lần, dùng lại cho nhiều
        # ngày. Thêm món vào thực đơn một ngày cụ thể là COPY dữ liệu từ đây
        # sang menu_items (không tham chiếu thẳng), để sau này đổi giá gốc
        # không làm thay đổi ngược các ngày đã áp dụng trước đó.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS restaurant_menu_catalog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                restaurant_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                tags TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
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
                note TEXT,
                FOREIGN KEY (order_id) REFERENCES orders (id),
                FOREIGN KEY (menu_item_id) REFERENCES menu_items (id)
            )
        """)

        # Quỹ chung: bảng một dòng duy nhất (id luôn = 1) để đọc số dư nhanh mà
        # không phải cộng dồn toàn bộ fund_transactions mỗi lần hỏi.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fund (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                balance INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT
            )
        """)

        # Sổ đối soát: mỗi dòng là một lần nạp/rút, không sửa/xoá được sau khi
        # ghi — muốn điều chỉnh thì ghi thêm một dòng bù trừ, giữ đúng vết kiểm toán.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fund_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                amount INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
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

        # Trung tâm thông báo: một dòng có thể gửi cho một người (target_user_id),
        # một vai trò (target_role, vd 'admin'), hoặc mọi người (cả hai đều NULL).
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT,
                target_user_id INTEGER,
                target_role TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (target_user_id) REFERENCES users (id)
            )
        """)

        # Đã đọc hay chưa là theo từng người xem, không phải theo thông báo —
        # một thông báo chung có thể người này đã đọc, người kia chưa.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_reads (
                notification_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                read_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (notification_id, user_id),
                FOREIGN KEY (notification_id) REFERENCES notifications (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Sổ ghi vết: chỉ thêm dòng, không sửa/xoá — dùng để tra lại sau này
        # "ai claim/gỡ ngày nào", "ai xoá món/quán nào" khi có tranh chấp, thay
        # vì phải suy đoán từ trạng thái hiện tại (vốn không giữ lịch sử).
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_id INTEGER,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (actor_id) REFERENCES users (id)
            )
        """)

    def _migrate_columns(self, cursor):
        """Thêm các cột mới lên bảng cũ đã tồn tại từ trước — cho DB có sẵn dữ liệu, không mất gì."""
        for column, ddl in [
            ("phone", "TEXT"), ("qr_image_url", "TEXT"), ("google_sub", "TEXT"),
            ("reset_token", "TEXT"), ("reset_expires", "TEXT"), ("team_id", "INTEGER"),
        ]:
            self._add_column_if_missing(cursor, "users", column, ddl)

        for column, ddl in [
            ("restaurant_id", "INTEGER"), ("image_url", "TEXT"),
            # Thẻ phân loại/tìm kiếm món, cách nhau bằng dấu phẩy (mã tìm kiếm/tag Phase 4)
            ("tags", "TEXT"), ("team_id", "INTEGER"),
        ]:
            self._add_column_if_missing(cursor, "menu_items", column, ddl)

        self._add_column_if_missing(cursor, "restaurants", "team_id", "INTEGER")
        self._add_column_if_missing(cursor, "restaurant_menu_catalog", "team_id", "INTEGER")
        self._add_column_if_missing(cursor, "order_owners", "team_id", "INTEGER")
        self._add_column_if_missing(cursor, "deadline_config", "team_id", "INTEGER")

        for column, ddl in [
            ("payment_method", "TEXT DEFAULT 'cash'"), ("locked_at", "TEXT"),
            ("paid_at", "TEXT"), ("payment_confirmed_at", "TEXT"),
            # Phần ship chia đều cho đơn này (mã 4.3) — mặc định 0 cho đơn cũ
            ("shipping_share", "INTEGER DEFAULT 0"), ("team_id", "INTEGER"),
        ]:
            self._add_column_if_missing(cursor, "orders", column, ddl)

        self._add_column_if_missing(cursor, "order_items", "note", "TEXT")

        # Tháng góp quỹ (dạng "YYYY-MM"), chỉ có giá trị ở dòng type='dues'
        self._add_column_if_missing(cursor, "fund_transactions", "month", "TEXT")
        # `fund` vẫn là 1 dòng duy nhất (CHECK id=1) — tách quỹ theo team cần
        # dựng lại bảng (PK/CHECK), CHƯA làm ở đây để không đụng dữ liệu quỹ
        # thật đang có; chỉ ghi team_id lên fund_transactions để biết giao
        # dịch nào của team nào khi tách sau này.
        self._add_column_if_missing(cursor, "fund_transactions", "team_id", "INTEGER")

    def _create_indexes(self, cursor):
        """Index cho các cột hay lọc/join nhất — không phải ràng buộc, chỉ để truy vấn nhanh hơn."""
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_reset ON users (reset_token)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_date ON orders (order_date)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_menu_items_date ON menu_items (available_date)"
        )
        # Truy vấn hay gặp nhất là "vai trò của user X", nên đánh index theo user_id
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles (user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles (role)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_fund_tx_created ON fund_transactions (created_at)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_fund_tx_month ON fund_transactions (month)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications (created_at)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_notification_reads_user "
            "ON notification_reads (user_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_catalog_restaurant "
            "ON restaurant_menu_catalog (restaurant_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_log_entity "
            "ON audit_log (entity_type, entity_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log (created_at)"
        )

    def _create_constraints(self, cursor):
        """Ràng buộc ở tầng DB cho các bất biến trước giờ chỉ kiểm bằng code —
        để 2 request ghi đồng thời (hoặc script/migration sau này đụng thẳng
        vào DB) không thể lách qua tầng service mà phá vỡ dữ liệu.

        Bọc try/except vì `CREATE UNIQUE INDEX` sẽ báo lỗi nếu DB đang có sẵn
        dữ liệu vi phạm (từ trước khi có ràng buộc này) — không muốn cả app
        không khởi động được chỉ vì vài dòng dữ liệu cũ, log lại để dọn sau.
        """
        # Mỗi nhân viên chỉ có 1 đơn cho 1 ngày — OrderService.place_order() đã
        # coi đây là bất biến (tìm đơn gần nhất rồi ghi đè), giờ ép luôn ở DB.
        try:
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_user_date "
                "ON orders (user_id, order_date)"
            )
        except sqlite3.IntegrityError:
            pass

        # Mỗi ngày chỉ đặt 1 quán — MenuService._assert_single_restaurant() đã
        # kiểm bằng code khi thêm/sửa món; trigger này là lưới an toàn ở tầng
        # DB, không thay thế thông báo lỗi thân thiện phía service.
        #
        # DROP rồi tạo lại (thay vì IF NOT EXISTS) vì trigger UPDATE bên dưới
        # từng có bug: MenuRepository.update() luôn set available_date VÀ
        # restaurant_id trong SET dù người dùng chỉ sửa tên/giá — trigger cũ
        # so sánh restaurant_id khác NEW.id mà không loại trừ trường hợp
        # KHÔNG đổi gì cả, nên sửa tên món ở một ngày đã lỡ có dữ liệu sai
        # (2 quán cùng ngày, từ trước khi có trigger này) sẽ bị ABORT oan dù
        # không hề đổi quán/ngày. Thêm điều kiện "thực sự đổi giá trị" để
        # không chặn nhầm các UPDATE không đổi restaurant_id/available_date.
        cursor.execute("DROP TRIGGER IF EXISTS trg_menu_items_single_restaurant_insert")
        cursor.execute("DROP TRIGGER IF EXISTS trg_menu_items_single_restaurant_update")
        cursor.execute("""
            CREATE TRIGGER trg_menu_items_single_restaurant_insert
            BEFORE INSERT ON menu_items
            FOR EACH ROW
            WHEN NEW.restaurant_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM menu_items
                WHERE available_date = NEW.available_date
                  AND restaurant_id IS NOT NULL
                  AND restaurant_id != NEW.restaurant_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'Mỗi ngày chỉ đặt được 1 quán');
            END
        """)
        cursor.execute("""
            CREATE TRIGGER trg_menu_items_single_restaurant_update
            BEFORE UPDATE OF available_date, restaurant_id ON menu_items
            FOR EACH ROW
            WHEN NOT (NEW.available_date IS OLD.available_date AND NEW.restaurant_id IS OLD.restaurant_id)
                 AND NEW.restaurant_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM menu_items
                WHERE available_date = NEW.available_date
                  AND restaurant_id IS NOT NULL
                  AND restaurant_id != NEW.restaurant_id
                  AND id != NEW.id
            )
            BEGIN
                SELECT RAISE(ABORT, 'Mỗi ngày chỉ đặt được 1 quán');
            END
        """)

    def _seed_fund(self, cursor):
        """Dòng số dư quỹ khởi tạo — chạy trước mọi thao tác đọc/ghi quỹ."""
        cursor.execute("INSERT OR IGNORE INTO fund (id, balance, updated_at) VALUES (1, 0, NULL)")

    def _seed_default_team(self, cursor):
        """Tạo sẵn 1 team mặc định (id=1) rồi gán cho mọi dòng còn NULL —
        idempotent, an toàn gọi lại nhiều lần. Chưa dùng để lọc dữ liệu gì cả,
        chỉ đảm bảo team_id có giá trị thay vì để trống mãi."""
        cursor.execute("INSERT OR IGNORE INTO teams (id, name) VALUES (1, 'Văn phòng chính')")

        for table in (
            "users", "restaurants", "restaurant_menu_catalog", "menu_items",
            "orders", "order_owners", "deadline_config", "fund_transactions",
        ):
            cursor.execute(f"UPDATE {table} SET team_id = 1 WHERE team_id IS NULL")

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
