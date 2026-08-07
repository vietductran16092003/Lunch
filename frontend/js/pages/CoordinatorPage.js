import { DatePicker } from "../components/DatePicker.js";
import { GroupedOrdersView } from "../components/GroupedOrdersView.js";
import { MenuGrid } from "../components/MenuGrid.js";
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
    this.assistGrid = new MenuGrid("assist-menu-grid", (selection) => this.renderAssistTotals(selection));
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
    Dom.byId("poll-create-form").addEventListener("submit", (e) => this.createPoll(e));
    Dom.byId("assist-order-btn").addEventListener("click", () => this.placeOrderForEmployee());
    Dom.byId("broadcast-form").addEventListener("submit", (e) => this.sendBroadcast(e));

    await this.loadDates();
    await Promise.all([
      this.loadGrouped(), this.loadSummary(), this.loadReminders(),
      this.loadPoll(), this.loadEmployees(), this.loadAssistMenu(), this.loadPredict(),
    ]);

    this.listen({
      order_placed: () => { this.loadGrouped(); this.loadSummary(); this.loadReminders(); },
      order_updated: () => { this.loadGrouped(); this.loadSummary(); },
      order_cancelled: () => { this.loadGrouped(); this.loadSummary(); this.loadReminders(); },
      orders_locked: () => { this.loadGrouped(); this.loadReminders(); },
      shipping_split: (data) => {
        if (data.date === this.date) this.loadGrouped();
      },
      poll_opened: () => this.loadPoll(),
      poll_voted: () => this.loadPoll(),
      poll_closed: () => this.loadPoll(),
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
    await Promise.all([
      this.loadGrouped(), this.loadSummary(), this.loadReminders(),
      this.loadPoll(), this.loadAssistMenu(), this.loadPredict(),
    ]);
  }

  async loadPredict() {
    const box = Dom.byId("ai-predict-box");
    if (!box) return;
    try {
      const data = await api.get(`/ai/predict?date=${encodeURIComponent(this.date)}`);
      Dom.clear(box);
      box.appendChild(Dom.el("p", { style: "margin:0;", text: data.message }));
      if (data.has_data && data.likely_items.length) {
        box.appendChild(
          Dom.el(
            "p",
            { style: "margin:8px 0 0;" },
            "Món hay được đặt: " +
              data.likely_items.map((i) => `${i.name} (~${i.avg_quantity})`).join(", ")
          )
        );
      }
    } catch (err) {
      Dom.clear(box).appendChild(Dom.emptyState("⚠️", "Không tải được dự đoán."));
    }
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

  // ===== Bình chọn quán ăn (Phase 4) =====

  async loadPoll() {
    const box = Dom.byId("poll-box");
    if (!box) return;
    try {
      const data = await api.get(`/polls/current?date=${encodeURIComponent(this.date)}`);
      this.renderPoll(box, data.poll);
    } catch (err) {
      Dom.clear(box).appendChild(Dom.emptyState("⚠️", "Không tải được bình chọn."));
    }
  }

  renderPoll(box, poll) {
    Dom.clear(box);
    if (!poll) {
      box.appendChild(Dom.el("p", { style: "margin:0;", text: "Chưa có bình chọn cho ngày này." }));
      return;
    }

    const rows = poll.options.map((opt) => {
      const pct = poll.total_votes ? Math.round((opt.votes / poll.total_votes) * 100) : 0;
      return Dom.el(
        "div",
        { style: "margin-bottom:8px;" },
        Dom.el("div", { style: "display:flex; justify-content:space-between;" },
          Dom.el("span", { text: opt.label }),
          Dom.el("span", { class: "mono", text: `${opt.votes} phiếu (${pct}%)` })
        )
      );
    });

    const closeBtn = poll.closed
      ? null
      : Dom.el("button", { type: "button", class: "ghost", text: "Đóng bình chọn" });
    if (closeBtn) {
      closeBtn.addEventListener("click", async () => {
        Dom.setBusy(closeBtn, true, "Đang đóng");
        try {
          await api.post(`/polls/${poll.id}/close`);
          toasts.info("Đã đóng bình chọn");
        } catch (err) {
          Dom.setBusy(closeBtn, false);
          toasts.error("Không đóng được", err.message);
        }
      });
    }

    box.append(
      Dom.el("p", { style: "margin:0 0 8px;" },
        Dom.el("strong", { text: poll.question }),
        poll.closed ? Dom.el("span", { class: "badge", style: "margin-left:8px;", text: "Đã đóng" }) : null
      ),
      ...rows,
      closeBtn
    );
  }

  async createPoll(event) {
    event.preventDefault();
    const question = Dom.byId("poll-question").value.trim();
    const optionsText = Dom.byId("poll-options").value;
    const message = Dom.byId("poll-create-message");
    const button = event.target.querySelector("button[type='submit']");

    const options = optionsText.split("\n").map((s) => s.trim()).filter(Boolean);
    if (options.length < 2) {
      message.className = "message-error";
      message.textContent = "Cần ít nhất 2 lựa chọn";
      return;
    }

    Dom.setBusy(button, true, "Đang mở bình chọn");
    try {
      await api.post("/polls", { question, options, poll_date: this.date });
      message.className = "message-success";
      message.textContent = "Đã mở bình chọn";
      toasts.success("Đã mở bình chọn");
      Dom.byId("poll-question").value = "";
      Dom.byId("poll-options").value = "";
      await this.loadPoll();
    } catch (err) {
      message.className = "message-error";
      message.textContent = err.message;
      toasts.error("Không mở được bình chọn", err.message);
    } finally {
      Dom.setBusy(button, false);
    }
  }

  // ===== Đặt hộ nhân viên (Phase 4) =====

  async loadEmployees() {
    const select = Dom.byId("assist-employee");
    if (!select) return;
    try {
      const data = await api.get("/coordinator/employees");
      Dom.clear(select);
      select.appendChild(Dom.el("option", { value: "", text: "— Chọn nhân viên —" }));
      (data.users || []).forEach((u) => {
        select.appendChild(Dom.el("option", { value: u.id, text: `${u.name} (${u.email})` }));
      });
    } catch (err) {
      // Danh sách trống thì form vẫn hiện, chỉ là chưa chọn được ai
    }
  }

  async loadAssistMenu() {
    try {
      const data = await api.get(`/menu?date=${encodeURIComponent(this.date)}`);
      this.assistGrid.render(data.items, { locked: false });
    } catch (err) {
      this.assistGrid.showError("Không tải được thực đơn.");
    }
  }

  renderAssistTotals(selection) {
    const total = selection.reduce((sum, i) => sum + i.price * i.quantity, 0);
    const count = selection.reduce((sum, i) => sum + i.quantity, 0);
    Dom.setText("assist-total", Formatter.money(total));
    Dom.setText("assist-count", count === 0 ? "Chưa chọn món nào" : `${count} phần`);
  }

  async placeOrderForEmployee() {
    const select = Dom.byId("assist-employee");
    const message = Dom.byId("assist-order-message");
    const button = Dom.byId("assist-order-btn");
    const selection = this.assistGrid.getSelection();

    if (!select.value) {
      message.className = "message-error";
      message.textContent = "Vui lòng chọn nhân viên";
      select.focus();
      return;
    }
    if (!selection.length) {
      message.className = "message-error";
      message.textContent = "Vui lòng chọn ít nhất một món";
      return;
    }

    Dom.setBusy(button, true, "Đang đặt hộ");
    try {
      await api.post(`/coordinator/orders-for/${select.value}`, {
        items: selection.map((i) => ({
          menu_item_id: i.menu_item_id, quantity: i.quantity, note: i.note || undefined,
        })),
        order_date: this.date,
      });
      message.className = "message-success";
      message.textContent = "Đã đặt hộ thành công";
      toasts.success("Đã đặt hộ", select.options[select.selectedIndex].text);
      this.assistGrid.render(this.assistGrid.items, { locked: false });
    } catch (err) {
      message.className = "message-error";
      message.textContent = err.message;
      toasts.error("Đặt hộ thất bại", err.message);
    } finally {
      Dom.setBusy(button, false);
    }
  }

  // ===== Thông báo chung (Phase 4) =====

  async sendBroadcast(event) {
    event.preventDefault();
    const input = Dom.byId("broadcast-message");
    const message = Dom.byId("broadcast-message-status");
    const button = event.target.querySelector("button[type='submit']");

    if (!input.value.trim()) {
      message.className = "message-error";
      message.textContent = "Vui lòng nhập nội dung";
      return;
    }

    Dom.setBusy(button, true, "Đang gửi");
    try {
      await api.post("/coordinator/broadcast", { message: input.value.trim() });
      message.className = "message-success";
      message.textContent = "Đã gửi thông báo";
      toasts.success("Đã gửi thông báo");
      input.value = "";
    } catch (err) {
      message.className = "message-error";
      message.textContent = err.message;
      toasts.error("Gửi thất bại", err.message);
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
