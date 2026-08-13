"""Nghiệp vụ AI/gợi ý (Phase 3), bản rule-based — chưa cần khoá API ngoài.

Tách riêng khỏi OrderService/MenuService vì đây là nhóm tính năng "phụ trợ":
gợi ý, tóm tắt, nhắc nhở, chatbot đều chỉ ĐỌC dữ liệu đã có và suy luận bằng
luật đơn giản. Khi có API key thật, chỉ cần thay phần suy luận bên trong từng
hàm, chữ ký hàm và route giữ nguyên.
"""

from datetime import date

from ..config import Config
from ..core.dates import Clock
from ..core.errors import ValidationError


class AiService:

    def __init__(self, order_repository, menu_repository, user_repository,
                 restaurant_repository, event_broker, deadline_service=None, config=Config):
        self.orders = order_repository
        self.menu = menu_repository
        self.users = user_repository
        self.restaurants = restaurant_repository
        self.events = event_broker
        self.deadlines = deadline_service
        self.config = config

    def _cutoff_for(self, target_date: str) -> str:
        if self.deadlines:
            return self.deadlines.cutoff_for(target_date)
        return self.config.cutoff_label()

    def _is_closed(self, target_date: str) -> bool:
        if self.deadlines:
            return self.deadlines.is_locked(target_date)
        return self.config.cutoff_passed_for(target_date)

    # ===== Gợi ý món (dựa trên tần suất đặt của chính người dùng) =====

    def suggest_items(self, user_id, target_date=None, limit: int = 5) -> dict:
        target_date = Clock.date_or_today(target_date)

        counts = {}
        for order in self.orders.list_for_user(user_id)[:30]:
            self.orders.with_items(order)
            for item in order.items:
                key = (item.name or "").strip().lower()
                if not key:
                    continue
                entry = counts.setdefault(key, {"name": item.name, "count": 0})
                entry["count"] += item.quantity or 1

        today_menu = {
            (mi.name or "").strip().lower(): mi for mi in self.menu.list_for_date(target_date)
        }

        ranked = sorted(counts.values(), key=lambda e: -e["count"])
        suggestions = []
        for entry in ranked:
            match = today_menu.get(entry["name"].strip().lower())
            if match is None:
                continue
            data = match.to_dict()
            data["order_count"] = entry["count"]
            suggestions.append(data)
            if len(suggestions) >= limit:
                break

        return {
            "date": target_date,
            "suggestions": suggestions,
            "based_on_orders": bool(counts),
        }

    # ===== Tóm tắt đơn trong ngày (cho treasurer/admin) =====

    def summarize_day(self, target_date=None) -> dict:
        target_date = Clock.date_or_today(target_date)
        orders = self.orders.list_for_date(target_date)

        item_counts = {}
        restaurant_totals = {}
        grand_total = 0
        people = set()

        for order in orders:
            people.add(order.user_id)
            for item in order.items:
                item_counts[item.name] = item_counts.get(item.name, 0) + item.quantity
                rname = item.restaurant_name or "Không rõ quán"
                restaurant_totals[rname] = restaurant_totals.get(rname, 0) + item.line_cost
                grand_total += item.line_cost

        top_items = sorted(item_counts.items(), key=lambda kv: -kv[1])[:5]
        top_restaurants = sorted(restaurant_totals.items(), key=lambda kv: -kv[1])[:3]

        lines = [
            f"Ngày {target_date}: {len(orders)} đơn từ {len(people)} người, "
            f"tổng {int(grand_total):,}đ."
        ]
        if top_items:
            lines.append("Món đặt nhiều nhất: " + ", ".join(f"{n} ({c})" for n, c in top_items) + ".")
        if top_restaurants:
            lines.append(
                "Quán chi nhiều nhất: "
                + ", ".join(f"{n} ({int(v):,}đ)" for n, v in top_restaurants) + "."
            )

        return {
            "date": target_date,
            "total_orders": len(orders),
            "total_people": len(people),
            "grand_total": grand_total,
            "top_items": [{"name": n, "count": c} for n, c in top_items],
            "top_restaurants": [{"name": n, "total": v} for n, v in top_restaurants],
            "summary_text": " ".join(lines),
        }

    # ===== Báo cáo AI theo khoảng ngày (Phase 4) =====

    def range_report(self, start_date, end_date=None) -> dict:
        """Tổng hợp chi tiêu và thói quen đặt món trong một khoảng ngày.

        Duyệt bằng list_for_date từng ngày thay vì viết SQL tổng hợp riêng, vì
        quy mô app này (vài chục đơn/ngày) không cần tối ưu, và tái dùng được
        logic đã có ở summarize_day cho từng ngày.
        """
        start_date = Clock.date_or_today(start_date)
        end_date = Clock.date_or_today(end_date) if end_date else start_date
        if end_date < start_date:
            raise ValidationError("Ngày kết thúc phải sau ngày bắt đầu")
        if (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days > 60:
            raise ValidationError("Khoảng ngày tối đa 60 ngày")

        item_counts = {}
        person_totals = {}
        daily_totals = {}
        grand_total = 0
        total_orders = 0

        current = start_date
        while current <= end_date:
            orders = self.orders.list_for_date(current)
            day_total = 0
            for order in orders:
                total_orders += 1
                name = self.users.find_by_id(order.user_id)
                name = name.name if name else "Không rõ"
                for item in order.items:
                    item_counts[item.name] = item_counts.get(item.name, 0) + item.quantity
                    person_totals[name] = person_totals.get(name, 0) + item.line_cost
                    day_total += item.line_cost
            if day_total:
                daily_totals[current] = day_total
            grand_total += day_total
            current = Clock.add_days(current, 1)

        top_items = sorted(item_counts.items(), key=lambda kv: -kv[1])[:5]
        top_spenders = sorted(person_totals.items(), key=lambda kv: -kv[1])[:5]
        avg_per_day = grand_total / max(len(daily_totals), 1)

        lines = [
            f"Từ {start_date} đến {end_date}: {total_orders} đơn, tổng chi {int(grand_total):,}đ, "
            f"trung bình {int(avg_per_day):,}đ/ngày có phát sinh đơn."
        ]
        if top_items:
            lines.append("Món phổ biến nhất: " + ", ".join(f"{n} ({c})" for n, c in top_items) + ".")
        if top_spenders:
            lines.append(
                "Chi nhiều nhất: "
                + ", ".join(f"{n} ({int(v):,}đ)" for n, v in top_spenders) + "."
            )

        return {
            "start_date": start_date,
            "end_date": end_date,
            "total_orders": total_orders,
            "grand_total": grand_total,
            "top_items": [{"name": n, "count": c} for n, c in top_items],
            "top_spenders": [{"name": n, "total": v} for n, v in top_spenders],
            "daily_totals": [{"date": d, "total": v} for d, v in sorted(daily_totals.items())],
            "report_text": " ".join(lines),
        }

    # ===== Nhắc tự động: ai chưa đặt trước giờ chốt (mã 3.5x) =====

    def pending_reminders(self, target_date=None) -> dict:
        target_date = Clock.date_or_today(target_date)

        if self._is_closed(target_date):
            return {"date": target_date, "closed": True, "pending_users": [], "pending_count": 0}

        menu_today = self.menu.list_for_date(target_date)
        if not menu_today:
            return {
                "date": target_date, "closed": False, "pending_users": [],
                "pending_count": 0, "note": "Chưa có thực đơn cho ngày này",
            }

        ordered_ids = {o.user_id for o in self.orders.list_for_date(target_date)}
        pending = [u for u in self.users.list_all() if u.id not in ordered_ids]

        return {
            "date": target_date,
            "closed": False,
            "cutoff": self._cutoff_for(target_date),
            "pending_users": [{"id": u.id, "name": u.name, "email": u.email} for u in pending],
            "pending_count": len(pending),
        }

    # ===== Chatbot hỏi đáp nhanh (rule-based) =====

    def chat_reply(self, user_id, message: str) -> dict:
        text = (message or "").strip().lower()
        today = Clock.today()

        if not text:
            return {"reply": "Bạn muốn hỏi gì về thực đơn, đơn hàng hay giờ chốt đơn?"}

        if any(k in text for k in ("giờ chốt", "cutoff", "hết hạn", "khi nào chốt")):
            cutoff = self._cutoff_for(today)
            return {"reply": f"Giờ chốt đơn hôm nay ({today}) là {cutoff}."}

        if any(k in text for k in ("đặt chưa", "đơn của tôi", "đã đặt")):
            order = self.orders.find_for_user_on(user_id, today)
            if order is None:
                return {"reply": "Bạn chưa đặt món cho hôm nay."}
            self.orders.with_items(order)
            names = ", ".join(i.name for i in order.items) or "chưa chọn món"
            return {"reply": f"Đơn hôm nay của bạn: {names}."}

        if any(k in text for k in ("thực đơn", "menu", "hôm nay có gì", "có món gì")):
            items = self.menu.list_for_date(today)
            if not items:
                return {"reply": "Hôm nay chưa có thực đơn."}
            names = ", ".join(i.name for i in items[:10])
            return {"reply": f"Thực đơn hôm nay có: {names}."}

        return {
            "reply": "Xin lỗi, mình chưa hiểu câu hỏi này. Bạn có thể hỏi: "
                     "\"thực đơn hôm nay có gì\", \"tôi đặt chưa\", hoặc \"giờ chốt đơn\"."
        }
