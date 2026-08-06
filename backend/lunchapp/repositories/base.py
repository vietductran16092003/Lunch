"""Lớp cha cho repository."""


class BaseRepository:
    """Mọi truy vấn SQL nằm ở tầng này, service không viết SQL.

    Repository nhận Database qua constructor nên đổi nguồn dữ liệu hay trỏ vào
    file test chỉ là chuyện truyền tham số khác.
    """

    def __init__(self, database):
        self.db = database

    # ----- Tiện ích -----

    def _fetch_one(self, sql, params=()):
        with self.db.session() as conn:
            return conn.execute(sql, params).fetchone()

    def _fetch_all(self, sql, params=()):
        with self.db.session() as conn:
            return conn.execute(sql, params).fetchall()

    def _execute(self, sql, params=()):
        """Chạy một câu ghi, trả về số dòng bị ảnh hưởng."""
        with self.db.session(commit=True) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.rowcount

    def _insert(self, sql, params=()):
        """Chạy một câu INSERT, trả về id vừa tạo."""
        with self.db.session(commit=True) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.lastrowid
