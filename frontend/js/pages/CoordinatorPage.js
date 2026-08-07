import { DatePicker } from "../components/DatePicker.js";
import { GroupedOrdersView } from "../components/GroupedOrdersView.js";
import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";
import { hasAnyRole } from "../core/roles.js";
import { toasts } from "../core/ToastManager.js";
import { BasePage } from "./BasePage.js";

/** Trang của người gom đơn: tổng hợp theo quán (4.2) và chia phí ship (4.3). */
export class CoordinatorPage extends BasePage {
  constructor() {
    super();
    this.date = Formatter.todayIso();
    this.today = this.date;
    this.availableDates = [];
    this.grouped = new GroupedOrdersView();
    this.datePicker = new DatePicker("coordinator-date-picker", (date) => this.switchDate(date));
  }

  async init() {
    if (!hasAnyRole(this.user, ["coordinator", "admin"])) {
      const main = Dom.byId("main");
      Dom.clear(main).append(
        Dom.el("h1", { text: "Gom đơn" }),
        Dom.notice(
          "warning",
          "Bạn không có quyền vào khu vực này",
          "Trang này dành cho người mang vai trò Người gom đơn. Liên hệ quản trị viên nếu bạn cần quyền."
        ),
        Dom.el("a", { class: "link-action", href: "index.html", text: "← Về trang thực đơn" })
      );
      return;
    }

    Dom.byId("shipping-split-form").addEventListener("submit", (e) => this.splitShipping(e));

    await this.loadDates();
    await Promise.all([this.loadGrouped(), this.loadSummary(), this.loadReminders()]);

    this.listen({
      order_placed: () => { this.loadGrouped(); this.loadSummary(); this.loadReminders(); },
      order_updated: () => { this.loadGrouped(); this.loadSummary(); },
      order_cancelled: () => { this.loadGrouped(); this.loadSummary(); this.loadReminders(); },
      orders_locked: () => { this.loadGrouped(); this.loadReminders(); },
      shipping_split: (data) => {
        if (data.date === this.date) this.loadGrouped();
      },
    });
  }

  async loadDates() {
    try {
      const data = await api.get("/menu/dates");
      this.today = data.today;
      this.availableDates = data.dates || [];
    } catch (err) {
      this.availableDates = [];
    }
    this.datePicker.render(this.availableDates, this.date, this.today);
  }

  async switchDate(date) {
    if (!date || date === this.date) return;
    this.date = date;
    this.datePicker.render(this.availableDates, this.date, this.today);
    await Promise.all([this.loadGrouped(), this.loadSummary(), this.loadReminders()]);
  }

  async loadSummary() {
    const box = Dom.byId("ai-summary-box");
    if (!box) return;
    try {
      const data = await api.get(`/ai/summary?date=${encodeURIComponent(this.date)}`);
      Dom.clear(box);
      box.appendChild(Dom.el("p", { style: "margin:0;", text: data.summary_text }));
    } catch (err) {
      Dom.clear(box).appendChild(Dom.emptyState("⚠️", "Không tải được tóm tắt."));
    }
  }

  async loadReminders() {
    const box = Dom.byId("ai-reminders-box");
    if (!box) return;
    try {
      const data = await api.get(`/ai/reminders?date=${encodeURIComponent(this.date)}`);
      Dom.clear(box);

      if (data.closed) {
        box.appendChild(Dom.el("p", { style: "margin:0;", text: "Đã quá giờ chốt đơn." }));
        return;
      }
      if (data.note) {
        box.appendChild(Dom.el("p", { style: "margin:0;", text: data.note }));
        return;
      }
      if (!data.pending_users.length) {
        box.appendChild(Dom.el("p", { style: "margin:0;", text: "Mọi người đã đặt món." }));
        return;
      }

      box.append(
        Dom.el("p", {
          style: "margin:0 0 8px;",
          text: `${data.pending_count} người chưa đặt (giờ chốt ${data.cutoff}):`,
        }),
        Dom.el(
          "ul",
          { style: "margin:0; padding-left:18px;" },
          ...data.pending_users.map((u) => Dom.el("li", { text: `${u.name} (${u.email})` }))
        )
      );
    } catch (err) {
      Dom.clear(box).appendChild(Dom.emptyState("⚠️", "Không tải được danh sách nhắc."));
    }
  }

  async loadGrouped() {
    try {
      const data = await api.get(`/coordinator/grouped?date=${encodeURIComponent(this.date)}`);
      this.grouped.render(data);
    } catch (err) {
      this.grouped.showError(err.message);
    }
  }

  async splitShipping(event) {
    event.preventDefault();
    const feeInput = Dom.byId("shipping-total-fee");
    const message = Dom.byId("shipping-split-message");
    const button = event.target.querySelector("button[type='submit']");

    feeInput.removeAttribute("aria-invalid");
    const fee = parseInt(feeInput.value, 10);
    if (!fee || fee <= 0) {
      feeInput.setAttribute("aria-invalid", "true");
      Dom.setText("shipping-fee-error", "Vui lòng nhập số tiền lớn hơn 0");
      feeInput.focus();
      return;
    }
    Dom.setText("shipping-fee-error", "");

    if (!window.confirm(
      `Chia ${Formatter.money(fee)} tiền ship cho các đơn đã chốt ngày ${this.date}?`
    )) {
      return;
    }

    Dom.setBusy(button, true, "Đang chia phí ship");
    try {
      const result = await api.post("/coordinator/split-shipping", {
        date: this.date, total_fee: fee,
      });

      message.className = "message-success";
      message.textContent =
        `Đã chia cho ${result.order_count} đơn, mỗi đơn ${Formatter.money(result.per_order)}.`;
      toasts.success("Đã chia phí ship", message.textContent);

      this.renderShippingResult(result);
      feeInput.value = "";
      await this.loadGrouped();
    } catch (err) {
      message.className = "message-error";
      message.textContent = err.message;
      toasts.error("Chia phí ship thất bại", err.message);
    } finally {
      Dom.setBusy(button, false);
    }
  }

  renderShippingResult(result) {
    const box = Dom.byId("shipping-result");
    Dom.clear(box);

    const tbody = Dom.el("tbody");
    (result.orders || []).forEach((o) => {
      tbody.appendChild(
        Dom.el(
          "tr",
          {},
          Dom.el("td", { text: o.user_name }),
          Dom.el("td", { class: "num mono", text: Formatter.money(o.shipping_share) })
        )
      );
    });

    const table = Dom.el("table", {
      html:
        "<caption>Phần ship từng người vừa được cộng thêm</caption>" +
        "<thead><tr><th scope='col'>Nhân viên</th><th scope='col' class='num'>Tiền ship</th></tr></thead>",
    });
    table.appendChild(tbody);
    box.appendChild(Dom.el("div", { class: "table-wrap" }, table));
  }
}
