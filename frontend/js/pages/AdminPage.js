import { DashboardView } from "../components/DashboardView.js";
import { DatePicker } from "../components/DatePicker.js";
import { GroupedOrdersView } from "../components/GroupedOrdersView.js";
import { MenuForm } from "../components/MenuForm.js";
import { PaymentInfoForm } from "../components/PaymentInfoForm.js";
import { RestaurantManager } from "../components/RestaurantManager.js";
import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";
import { toasts } from "../core/ToastManager.js";
import { BasePage } from "./BasePage.js";

/** Trang đặt hàng của người đứng ra đặt — cũng gộp luôn phần gom đơn (tóm tắt,
 * ai chưa đặt, tổng hợp theo quán, chia ship, thông báo) sau khi bỏ vai trò
 * điều phối viên riêng. */
export class AdminPage extends BasePage {
  constructor() {
    super();
    this.date = null;
    this.today = null;

    this.dashboard = new DashboardView({ onConfirmPayment: () => this.loadDashboard() });
    this.menuForm = new MenuForm({ onCreated: () => this.loadDashboard() });
    this.restaurants = new RestaurantManager({
      onChange: (list) => this.menuForm.updateAvailability(list.length > 0),
    });
    this.datePicker = new DatePicker("admin-date-picker", (date) => this.switchDate(date));
    this.paymentInfo = new PaymentInfoForm();
    this.grouped = new GroupedOrdersView();
  }

  async init() {
    Dom.byId("lock-orders-btn").addEventListener("click", () => this.lockOrders());
    Dom.byId("dashboard-refresh-btn").addEventListener("click", (e) => this.refresh(e));
    Dom.byId("shipping-split-form").addEventListener("submit", (e) => this.splitShipping(e));
    Dom.byId("broadcast-form").addEventListener("submit", (e) => this.sendBroadcast(e));

    await this.restaurants.load();
    await Promise.all([
      this.loadDashboard(), this.loadSummary(), this.loadReminders(), this.loadGrouped(),
    ]);

    this.listen({
      order_placed: (data) => {
        const when =
          data.is_advance && data.order_date ? ` · đặt trước cho ${data.order_date}` : "";
        toasts.info(
          data.updated ? "Có người sửa đơn" : "Có đơn mới",
          `${data.employee_name} · ${data.item_count} món${when}`
        );
        this.loadDashboard();
        this.loadSummary();
        this.loadReminders();
        this.loadGrouped();
      },
      payment_declared: (data) => {
        toasts.warning(
          "Có người báo đã chuyển khoản",
          `${data.employee_name} · ${Formatter.money(data.amount)} · cần bạn xác nhận`
        );
        this.loadDashboard();
      },
      payment_confirmed: () => this.loadDashboard(),
      order_cancelled: () => {
        this.loadDashboard();
        this.loadSummary();
        this.loadReminders();
        this.loadGrouped();
      },
      order_updated: () => {
        this.loadDashboard();
        this.loadSummary();
        this.loadGrouped();
      },
      orders_locked: () => {
        this.loadGrouped();
        this.loadReminders();
      },
      shipping_split: (data) => {
        if (data.date === this.date) this.loadGrouped();
      },
    });
  }

  async loadDashboard() {
    try {
      const query = this.date ? `?date=${encodeURIComponent(this.date)}` : "";
      const data = await api.get(`/admin/dashboard${query}`);

      this.date = data.date;
      this.today = data.today;
      this.renderDatePicker(data);
      this.dashboard.render(data);
    } catch (err) {
      this.dashboard.showError(() => this.loadDashboard());
    }
  }

  /** Dùng lại DatePicker của nhân viên, chỉ cần đưa về đúng dạng dữ liệu. */
  renderDatePicker(data) {
    const days = (data.available_dates || []).map((iso) => ({
      date: iso,
      item_count: 0,
      is_today: iso === data.today,
      closed: false,
      has_order: false,
    }));

    if (days.length < 2) {
      this.datePicker.render([], data.date, data.today);
      return;
    }

    // Bảng điều khiển không cần đếm món trên chip, chỉ cần ngày
    const container = Dom.byId("admin-date-picker");
    this.datePicker.render(days, data.date, data.today);
    container.querySelectorAll(".chip-meta").forEach((meta, index) => {
      meta.textContent = days[index].date;
    });
  }

  async switchDate(date) {
    if (!date || date === this.date) return;
    this.date = date;
    await Promise.all([
      this.loadDashboard(), this.loadSummary(), this.loadReminders(), this.loadGrouped(),
    ]);
  }

  async refresh(event) {
    const button = event.currentTarget;
    Dom.setBusy(button, true, "Đang làm mới");
    await this.loadDashboard();
    Dom.setBusy(button, false);
  }

  async lockOrders() {
    const button = Dom.byId("lock-orders-btn");
    const message = Dom.byId("lock-orders-message");

    if (!window.confirm("Chốt đơn? Sau bước này nhân viên không sửa đơn được nữa.")) return;

    Dom.setBusy(button, true, "Đang chốt đơn");
    try {
      const data = await api.post("/admin/orders/lock", { date: this.date });

      message.className = "message-success";
      message.textContent = `Đã chốt ${data.locked_count} đơn.`;

      const links = data.grab_links || [];
      if (links.length) {
        // Mở lần lượt, tránh trình duyệt chặn hàng loạt popup
        links.forEach((r, index) => {
          window.setTimeout(() => {
            window.open(r.grab_url, "_blank", "noopener,noreferrer");
          }, index * 400);
        });

        toasts.info(
          "Đang mở Grab",
          `${links.length} quán cần đặt: ${links.map((r) => r.name).join(", ")}`
        );

        // Đơn sang trạng thái chờ thanh toán, nhân viên thấy nút sáng lên
        await api.post("/admin/orders/grab-placed", { date: this.date });
      } else {
        message.className = "message-error";
        message.textContent =
          "Đã chốt đơn, nhưng chưa quán nào có đường dẫn Grab — hãy bổ sung ở mục 1.";
        toasts.warning(
          "Chưa có đường dẫn Grab",
          "Bổ sung đường dẫn GrabFood cho nhà hàng để mở tự động."
        );
      }

      await this.loadDashboard();
    } catch (err) {
      message.className = "message-error";
      message.textContent = err.message;
      toasts.error("Chốt đơn thất bại", err.message);
    } finally {
      Dom.setBusy(button, false);
    }
  }

  // ===== Tóm tắt nhanh + ai chưa đặt (gộp từ trang Gom đơn cũ) =====

  async loadSummary() {
    const box = Dom.byId("ai-summary-box");
    if (!box) return;
    try {
      const query = this.date ? `?date=${encodeURIComponent(this.date)}` : "";
      const data = await api.get(`/ai/summary${query}`);
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
      const query = this.date ? `?date=${encodeURIComponent(this.date)}` : "";
      const data = await api.get(`/ai/reminders${query}`);
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

  // ===== Tổng hợp theo quán + chia phí ship (gộp từ trang Gom đơn cũ) =====

  async loadGrouped() {
    try {
      const query = this.date ? `?date=${encodeURIComponent(this.date)}` : "";
      const data = await api.get(`/coordinator/grouped${query}`);
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

  // ===== Gửi thông báo (gộp từ trang Gom đơn cũ) =====

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
}
