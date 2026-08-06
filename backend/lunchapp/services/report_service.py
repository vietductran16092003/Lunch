"""Xuất báo cáo CSV."""

import csv
import io

from ..core.dates import Clock


class ReportService:
    HEADERS = [
        "Nhân viên", "Nhà hàng", "Món ăn", "Đơn giá", "Số lượng",
        "Thành tiền", "Nhân viên báo đã chuyển", "Người đặt đã xác nhận",
    ]

    def __init__(self, order_repository):
        self.orders = order_repository

    def orders_csv(self, target_date=None) -> tuple:
        """Trả về (nội dung CSV, tên file)."""
        target_date = Clock.date_or_today(target_date)
        rows = self.orders.export_rows(target_date)

        output = io.StringIO()
        output.write("﻿")  # BOM để Excel mở đúng tiếng Việt
        writer = csv.writer(output)
        writer.writerow(self.HEADERS)

        for r in rows:
            writer.writerow([
                r["employee_name"],
                r["restaurant_name"] or "",
                r["item_name"],
                r["price"],
                r["quantity"],
                r["price"] * r["quantity"],
                "Rồi" if r["paid_at"] else "Chưa",
                "Rồi" if r["payment_confirmed_at"] else "Chưa",
            ])

        return output.getvalue(), f"don-hang-{target_date}.csv"
