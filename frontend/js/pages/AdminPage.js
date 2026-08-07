import { DashboardView } from "../components/DashboardView.js";
import { DatePicker } from "../components/DatePicker.js";
import { MenuExtractForm } from "../components/MenuExtractForm.js";
import { MenuForm } from "../components/MenuForm.js";
import { PaymentInfoForm } from "../components/PaymentInfoForm.js";
import { RestaurantManager } from "../components/RestaurantManager.js";
import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";
import { toasts } from "../core/ToastManager.js";
import { BasePage } from "./BasePage.js";

/** Trang đặt hàng của người đứng ra đặt. */
export class AdminPage extends BasePage {
  constructor() {
    super();
    this.date = null;
    this.today = null;

    this.dashboard = new DashboardView({ onConfirmPayment: () => this.loadDashboard() });
    this.menuForm = new MenuForm({ onCreated: () => this.loadDashboard() });
    this.extractForm = new MenuExtractForm({ onSaved: () => this.loadDashboard() });
    this.restaurants = new RestaurantManager({
      onChange: (list) => {
        this.menuForm.updateAvailability(list.length > 0);
        this.extractForm.updateRestaurants(list);
      },
    });
    this.datePicker = new DatePicker("admin-date-picker", (date) => this.switchDate(date));
    this.paymentInfo = new PaymentInfoForm();
  }

  async init() {
    Dom.byId("lock-orders-btn").addEventListener("click", () => this.lockOrders());
    Dom.byId("dashboard-refresh-btn").addEventListener("click", (e) => this.refresh(e));

    await this.restaurants.load();
    await this.loadDashboard();

    this.listen({
      order_placed: (data) => {
        const when =
          data.is_advance && data.order_date ? ` · đặt trước cho ${data.order_date}` : "";
        toasts.info(
          data.updated ? "Có người sửa đơn" : "Có đơn mới",
          `${data.employee_name} · ${data.item_count} món${when}`
        );
        this.loadDashboard();
      },
      payment_declared: (data) => {
        toasts.warning(
          "Có người báo đã chuyển khoản",
          `${data.employee_name} · ${Formatter.money(data.amount)} · cần bạn xác nhận`
        );
        this.loadDashboard();
      },
      payment_confirmed: () => this.loadDashboard(),
      order_cancelled: () => this.loadDashboard(),
      order_updated: () => this.loadDashboard(),
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
    await this.loadDashboard();
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
}
