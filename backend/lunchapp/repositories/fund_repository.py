"""Truy vấn bảng fund (số dư duy nhất) và fund_transactions (sổ đối soát)."""

from ..models import FundTransaction
from .base import BaseRepository

_TX_COLUMNS = (
    "fund_transactions.id, fund_transactions.type, fund_transactions.amount, "
    "fund_transactions.user_id, users.name AS user_name, fund_transactions.note, "
    "fund_transactions.created_at"
)


class FundRepository(BaseRepository):

    # ===== Đọc =====

    def get_balance(self) -> int:
        row = self._fetch_one("SELECT balance FROM fund WHERE id = 1")
        return row["balance"] if row else 0

    def list_transactions(self, limit: int = 100) -> list:
        rows = self._fetch_all(
            f"""
            SELECT {_TX_COLUMNS}
            FROM fund_transactions
            LEFT JOIN users ON fund_transactions.user_id = users.id
            ORDER BY fund_transactions.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return FundTransaction.from_rows(rows)

    # ===== Ghi =====

    def record_transaction(self, type: str, amount: int, user_id, note: str,
                            created_at: str) -> int:
        """Cập nhật số dư và ghi sổ trong CÙNG một giao dịch.

        Không bao giờ được để lộ khoảnh khắc balance đã đổi mà dòng sổ sách
        chưa kịp ghi (hoặc ngược lại) — hai thao tác này phải cùng thành công
        hoặc cùng thất bại.
        """
        delta = amount if type == "topup" else -amount
        with self.db.session(commit=True) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE fund SET balance = balance + ?, updated_at = ? WHERE id = 1",
                (delta, created_at),
            )
            cursor.execute(
                "INSERT INTO fund_transactions (type, amount, user_id, note, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (type, amount, user_id, note, created_at),
            )
            return cursor.lastrowid
