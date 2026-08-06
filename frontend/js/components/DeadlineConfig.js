import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";
import { toasts } from "../core/ToastManager.js";

/**
 * Cấu hình giờ chốt đơn theo từng ngày + đếm ngược (mã 4.1).
 *
 * Đồng hồ đếm ngược chạy phía client mỗi giây, nhưng mốc thời gian và trạng thái
 * khoá luôn lấy từ server — client chỉ hiển thị, không tự quyết định đã chốt hay chưa.
 */
export class DeadlineConfig {
  constructor({ canEdit = false, onSaved } = {}) {
    this.panel = Dom.byId("deadline-panel");
    this.canEdit = canEdit;
    this.onSaved = onSaved || (() => {});
    this.state = null;
    this.timer = null;
    this.date = null;
  }

  async load(date = null) {
    if (!this.panel) return;
    this.date = date || this.date;

    try {
      const query = this.date ? `?date=${encodeURIComponent(this.date)}` : "";
      this.state = await api.get(`/deadline${query}`);
      this.date = this.state.date;
      this.render();
      this.startCountdown();
    } catch (err) {
      Dom.clear(this.panel).appendChild(
        Dom.emptyState("⏱️", `Không tải được cấu hình giờ chốt. ${err.message}`)
      );
    }
  }

  render() {
    Dom.clear(this.panel);

    this.countdownBox = Dom.el(
      "div",
      { class: "countdown" },
      Dom.el("div", { class: "countdown-value", id: "countdown-value", text: "--:--:--" }),
      Dom.el("div", { class: "countdown-label", id: "countdown-label", text: "đang tính…" })
    );

    this.panel.append(this.countdownBox, this.buildForm());
    this.tick();
  }

  buildForm() {
    const s = this.state;

    const dateInput = Dom.el("input", {
      type: "date",
      id: "deadline-date",
      value: s.date,
      disabled: !this.canEdit,
    });
    dateInput.addEventListener("change", () => this.load(dateInput.value));

    const timeInput = Dom.el("input", {
      type: "time",
      id: "deadline-time",
      value: s.cutoff,
      disabled: !this.canEdit,
      "aria-describedby": "deadline-time-help",
    });

    const autoLock = Dom.el("input", {
      type: "checkbox",
      id: "deadline-auto-lock",
      disabled: !this.canEdit,
    });
    autoLock.checked = Boolean(s.auto_lock);

    const form = Dom.el(
      "form",
      { class: "deadline-form", style: "background:none; border:none; padding:0;" },
      Dom.el(
        "div",
        { class: "field" },
        Dom.el("label", { for: "deadline-date", text: "Ngày áp dụng" }),
        dateInput
      ),
      Dom.el(
        "div",
        { class: "field" },
        Dom.el("label", { for: "deadline-time", text: "Giờ chốt đơn" }),
        timeInput,
        Dom.el("span", {
          class: "helper",
          id: "deadline-time-help",
          text:
            s.source === "custom"
              ? "Ngày này đang dùng giờ riêng."
              : `Đang dùng giờ mặc định của hệ thống (${s.cutoff}).`,
        })
      ),
      Dom.el(
        "label",
        { class: "switch-field", for: "deadline-auto-lock" },
        autoLock,
        Dom.el(
          "span",
          { class: "switch-text" },
          Dom.el("span", { class: "switch-title", text: "Tự động chốt khi tới giờ" }),
          Dom.el("span", {
            class: "switch-hint",
            text: "Quá giờ là nhân viên không đặt/sửa/huỷ được nữa, không cần ai bấm tay.",
          })
        )
      )
    );

    if (this.canEdit) {
      const save = Dom.el("button", { type: "submit", text: "Lưu giờ chốt" });
      const message = Dom.el("p", {
        id: "deadline-message",
        role: "status",
        "aria-live": "polite",
        style: "margin:0;",
      });
      form.append(save, message);
      form.addEventListener("submit", (e) =>
        this.save(e, { dateInput, timeInput, autoLock, save, message })
      );
    } else {
      form.appendChild(
        Dom.el("p", { class: "subtitle", style: "margin:0;", text: "Chỉ quản trị viên đổi được giờ chốt." })
      );
    }

    return form;
  }

  async save(event, refs) {
    event.preventDefault();
    Dom.setBusy(refs.save, true, "Đang lưu giờ chốt");

    try {
      this.state = await api.put("/admin/deadline", {
        date: refs.dateInput.value,
        cutoff: refs.timeInput.value,
        auto_lock: refs.autoLock.checked,
      });
      this.date = this.state.date;

      refs.message.className = "message-success";
      refs.message.textContent = `Đã lưu giờ chốt ${this.state.cutoff} cho ngày ${this.state.date}`;
      toasts.success("Đã lưu giờ chốt", `${Formatter.shortDate(this.state.date)} · ${this.state.cutoff}`);

      this.render();
      this.startCountdown();
      await this.onSaved(this.state);
    } catch (err) {
      refs.message.className = "message-error";
      refs.message.textContent = err.message;
      Dom.setBusy(refs.save, false);
    }
  }

  // ===== Đếm ngược =====

  startCountdown() {
    this.stopCountdown();
    this.timer = window.setInterval(() => this.tick(), 1000);
  }

  stopCountdown() {
    if (this.timer) {
      window.clearInterval(this.timer);
      this.timer = null;
    }
  }

  tick() {
    const value = Dom.byId("countdown-value");
    const label = Dom.byId("countdown-label");
    if (!value || !label || !this.state) return;

    const target = new Date(`${this.state.date}T${this.state.cutoff}:00`);
    const remaining = target - new Date();

    this.countdownBox.classList.remove("is-urgent", "is-closed");

    if (this.state.locked || remaining <= 0) {
      value.textContent = "Đã chốt";
      label.textContent = `Giờ chốt ${this.state.cutoff} · ${Formatter.shortDate(this.state.date)}`;
      this.countdownBox.classList.add("is-closed");
      this.stopCountdown();
      return;
    }

    const totalSeconds = Math.floor(remaining / 1000);
    const hours = String(Math.floor(totalSeconds / 3600)).padStart(2, "0");
    const minutes = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, "0");
    const seconds = String(totalSeconds % 60).padStart(2, "0");

    value.textContent = `${hours}:${minutes}:${seconds}`;
    label.textContent = `còn lại tới ${this.state.cutoff}`;

    // Dưới 30 phút thì đổi màu VÀ đổi chữ, không chỉ dựa vào màu
    if (totalSeconds <= 1800) {
      this.countdownBox.classList.add("is-urgent");
      label.textContent = `sắp hết giờ — còn lại tới ${this.state.cutoff}`;
    }
  }
}
