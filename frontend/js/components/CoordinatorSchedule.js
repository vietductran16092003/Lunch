import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";
import { toasts } from "../core/ToastManager.js";

/**
 * Lịch tua người gom đơn 14 ngày tới (mã 1.6).
 *
 * Quản trị viên đổi người phụ trách ngay trên từng ngày; người khác chỉ xem.
 */
export class CoordinatorSchedule {
  static DAYS_AHEAD = 13;

  constructor(containerId = "schedule-list", { canEdit = false } = {}) {
    this.container = Dom.byId(containerId);
    this.canEdit = canEdit;
    this.today = null;
    this.schedule = [];
    this.candidates = [];
  }

  async load() {
    if (!this.container) return;

    try {
      // Chỉ quản trị viên mới lấy được danh sách ứng viên; người xem thường bỏ qua
      const [scheduleData, candidates] = await Promise.all([
        api.get("/coordinator/schedule"),
        this.canEdit ? this.loadCandidates() : Promise.resolve([]),
      ]);

      this.today = scheduleData.today;
      this.schedule = scheduleData.schedule || [];
      this.candidates = candidates;
      this.render(scheduleData);
    } catch (err) {
      Dom.clear(this.container).appendChild(
        Dom.emptyState("📅", `Không tải được lịch gom đơn. ${err.message}`)
      );
    }
  }

  async loadCandidates() {
    try {
      const data = await api.get("/admin/users");
      // Chỉ người mang vai trò coordinator mới được gán vào lịch
      return (data.users || []).filter((u) => u.roles.includes("coordinator"));
    } catch (err) {
      return [];
    }
  }

  render(data) {
    Dom.clear(this.container);

    const banner = Dom.byId("schedule-today");
    if (banner) {
      const who = data.today_coordinator;
      Dom.clear(banner).appendChild(
        who
          ? Dom.notice("info", "Người gom đơn hôm nay", who.user_name)
          : Dom.notice(
              "warning",
              "Hôm nay chưa có người gom đơn",
              "Hãy gán một người vào ngày hôm nay để tránh sót đơn."
            )
      );
    }

    if (this.canEdit && !this.candidates.length) {
      this.container.appendChild(
        Dom.notice(
          "warning",
          "Chưa ai có vai trò Người gom đơn",
          "Gán vai trò ở mục Phân quyền phía trên rồi quay lại đây."
        )
      );
      return;
    }

    const byDate = new Map(this.schedule.map((s) => [s.date, s]));
    const grid = Dom.el("div", { class: "schedule-list" });

    this.eachDate().forEach((iso) => {
      grid.appendChild(this.buildDay(iso, byDate.get(iso)));
    });

    this.container.appendChild(grid);
  }

  /** 14 ngày liên tiếp tính từ hôm nay (theo giờ địa phương). */
  eachDate() {
    const dates = [];
    for (let i = 0; i <= CoordinatorSchedule.DAYS_AHEAD; i += 1) {
      dates.push(Formatter.addDays(this.today, i));
    }
    return dates;
  }

  buildDay(iso, entry) {
    const parsed = new Date(`${iso}T00:00:00`);
    const isToday = iso === this.today;
    const isWeekend = parsed.getDay() === 0 || parsed.getDay() === 6;

    const card = Dom.el("div", {
      class:
        "schedule-day" + (isToday ? " is-today" : "") + (isWeekend ? " is-weekend" : ""),
    });

    card.appendChild(
      Dom.el(
        "div",
        { class: "day-head" },
        Dom.el(
          "div",
          {},
          Dom.el("div", { class: "day-name", text: Formatter.dayLabel(iso, this.today) }),
          Dom.el("div", { class: "day-date", text: Formatter.shortDate(iso) })
        ),
        isToday ? Dom.el("span", { class: "day-today-flag", text: "HÔM NAY" }) : null
      )
    );

    if (this.canEdit) {
      card.appendChild(this.buildSelect(iso, entry));
    } else {
      card.appendChild(
        entry
          ? Dom.el("div", { style: "font-weight:600;", text: entry.user_name })
          : Dom.el("div", { class: "day-unassigned", text: "Chưa gán người gom đơn" })
      );
    }

    return card;
  }

  buildSelect(iso, entry) {
    const select = Dom.el("select", {
      "aria-label": `Người gom đơn ngày ${Formatter.shortDate(iso)}`,
    });

    select.appendChild(Dom.el("option", { value: "", text: "— Chưa gán —" }));
    this.candidates.forEach((user) => {
      select.appendChild(Dom.el("option", { value: String(user.id), text: user.name }));
    });
    select.value = entry ? String(entry.user_id) : "";

    select.addEventListener("change", () => this.assign(iso, select));
    return select;
  }

  async assign(iso, select) {
    const userId = select.value;
    const previous = select.dataset.previous || "";
    select.disabled = true;

    try {
      if (userId) {
        const saved = await api.put("/admin/coordinator/schedule", {
          date: iso,
          user_id: parseInt(userId, 10),
        });
        toasts.success("Đã gán người gom đơn", `${Formatter.shortDate(iso)} · ${saved.user_name}`);
      } else {
        await api.delete(`/admin/coordinator/schedule/${iso}`);
        toasts.info("Đã bỏ gán", `Ngày ${Formatter.shortDate(iso)} chưa có người gom đơn`);
      }
      select.dataset.previous = userId;
      await this.load();
    } catch (err) {
      select.value = previous;
      toasts.error("Không lưu được lịch", err.message);
    } finally {
      select.disabled = false;
    }
  }
}
