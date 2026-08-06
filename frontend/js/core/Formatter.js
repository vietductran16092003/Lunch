const WEEKDAYS = ["Chủ nhật", "Thứ hai", "Thứ ba", "Thứ tư", "Thứ năm", "Thứ sáu", "Thứ bảy"];

/** Định dạng tiền, ngày giờ theo tiếng Việt. */
export class Formatter {
  static money(value) {
    return `${Number(value || 0).toLocaleString("vi-VN")} đ`;
  }

  /** "2026-08-05" -> "05/08" */
  static shortDate(iso) {
    if (!iso) return "";
    const [, month, day] = iso.split("-");
    return `${day}/${month}`;
  }

  /** Hôm nay / Ngày mai / Thứ mấy, so với mốc `today`. */
  static dayLabel(iso, today) {
    if (!iso) return "";
    if (iso === today) return "Hôm nay";

    const target = new Date(`${iso}T00:00:00`);
    const base = new Date(`${today}T00:00:00`);
    const diffDays = Math.round((target - base) / 86400000);

    if (diffDays === 1) return "Ngày mai";
    if (diffDays === -1) return "Hôm qua";
    return WEEKDAYS[target.getDay()] || iso;
  }

  /** Mốc thời gian đầy đủ, ví dụ "15:09 04/08/2026". */
  static moment(value) {
    if (!value) return "";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleString("vi-VN", {
      hour: "2-digit",
      minute: "2-digit",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  }

  static todayIso() {
    return new Date().toISOString().slice(0, 10);
  }
}
