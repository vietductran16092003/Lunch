import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";

/** Dải chọn ngày. Chỉ hiện khi có từ 2 ngày trở lên để đỡ rối. */
export class DatePicker {
  constructor(containerId, onSelect, titleId = null, onDelete = null) {
    this.container = Dom.byId(containerId);
    this.title = titleId ? Dom.byId(titleId) : null;
    this.onSelect = onSelect;
    // Có onDelete thì mọi chip TRỪ hôm nay đều có dấu x để gỡ bỏ hẳn ngày đó
    this.onDelete = onDelete;
  }

  render(days, selectedDate, today) {
    if (!this.container) return;

    if (!days || days.length < 2) {
      this.container.hidden = true;
      if (this.title) this.title.hidden = true;
      Dom.clear(this.container);
      return;
    }

    this.container.hidden = false;
    if (this.title) this.title.hidden = false;
    Dom.clear(this.container);
    days.forEach((day) => {
      this.container.appendChild(this.buildChip(day, selectedDate, today));
    });
  }

  buildChip(day, selectedDate, today) {
    const label = Formatter.dayLabel(day.date, today);
    const short = Formatter.shortDate(day.date);
    const state = day.closed ? "đã quá giờ chốt" : "còn đặt được";

    const chip = Dom.el(
      "button",
      {
        type: "button",
        class: `date-chip${day.closed ? " is-closed" : ""}`,
        "aria-pressed": String(day.date === selectedDate),
        "aria-label":
          `${label} ${short}, ${day.item_count} món, ${state}` +
          (day.has_order ? ", bạn đã đặt" : ""),
      },
      Dom.el("span", { class: "chip-day", text: `${label} · ${short}` }),
      Dom.el("span", {
        class: "chip-meta",
        text: day.closed ? `Đã chốt · ${day.item_count} món` : `${day.item_count} món`,
      }),
      day.has_order ? Dom.el("span", { class: "chip-flag", text: "✓ ĐÃ ĐẶT" }) : null
    );

    chip.addEventListener("click", () => this.onSelect(day.date));

    if (this.onDelete && day.date !== today && day.can_delete !== false) {
      const remove = Dom.el("span", {
        class: "chip-remove",
        role: "button",
        tabindex: "0",
        "aria-label": `Gỡ bỏ ngày ${short}`,
        text: "✕",
      });
      const trigger = (e) => {
        e.stopPropagation();
        this.onDelete(day.date);
      };
      remove.addEventListener("click", trigger);
      remove.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          trigger(e);
        }
      });
      chip.appendChild(remove);
    }

    return chip;
  }
}
