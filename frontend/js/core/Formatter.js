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

  /**
   * Ngày dạng YYYY-MM-DD theo giờ ĐỊA PHƯƠNG.
   *
   * Không dùng toISOString(): hàm đó quy về UTC nên ở múi giờ +7 sẽ trả về ngày
   * hôm trước trong khoảng 00:00–07:00 sáng.
   */
  static toIsoDate(value) {
    const d = value instanceof Date ? value : new Date(value);
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${d.getFullYear()}-${month}-${day}`;
  }

  static todayIso() {
    return Formatter.toIsoDate(new Date());
  }

  /** Cộng thêm `days` ngày vào một chuỗi YYYY-MM-DD, trả về chuỗi cùng dạng. */
  static addDays(iso, days) {
    const d = new Date(`${iso}T00:00:00`);
    d.setDate(d.getDate() + days);
    return Formatter.toIsoDate(d);
  }
}
