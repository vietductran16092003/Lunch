"""Truy vấn bảng order_owners — ai đứng ra đặt của một ngày."""

from .base import BaseRepository


class OrderOwnerRepository(BaseRepository):

    def get_owner(self, order_date: str):
        """Trả về user_id đang phụ trách ngày này, hoặc None nếu chưa ai nhận."""
        row = self._fetch_one(
            "SELECT user_id FROM order_owners WHERE order_date = ?", (order_date,)
        )
        return row["user_id"] if row else None

    def claim(self, order_date: str, user_id, claimed_at: str):
        """Chỉ ghi nếu ngày đó chưa ai nhận — người đầu tiên thêm món là người thắng."""
        self._execute(
            "INSERT OR IGNORE INTO order_owners (order_date, user_id, set_at) VALUES (?, ?, ?)",
            (order_date, user_id, claimed_at),
        )

    def list_from(self, from_date: str) -> list:
        """Người phụ trách của mọi ngày từ from_date trở đi — dùng để tô đúng
        dấu x gỡ ngày trên dải chọn ngày (chỉ chủ ngày/admin mới thấy)."""
        return self._fetch_all(
            "SELECT order_date, user_id FROM order_owners WHERE order_date >= ?",
            (from_date,),
        )

    def clear(self, order_date: str):
        """Gỡ người phụ trách — dùng khi xoá hẳn một ngày đã lỡ dựng."""
        self._execute("DELETE FROM order_owners WHERE order_date = ?", (order_date,))
