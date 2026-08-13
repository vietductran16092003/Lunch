import { CatalogManager } from "../components/CatalogManager.js";
import { DashboardView } from "../components/DashboardView.js";
import { DatePicker } from "../components/DatePicker.js";
import { MenuFromCatalog } from "../components/MenuFromCatalog.js";
import { MenuItemsList } from "../components/MenuItemsList.js";
import { PaymentInfoForm } from "../components/PaymentInfoForm.js";
import { RestaurantManager } from "../components/RestaurantManager.js";
import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";
import { toasts } from "../core/ToastManager.js";
import { BasePage } from "./BasePage.js";

/** Trang đặt hàng của người đứng ra đặt — cũng gộp luôn phần gom đơn (tóm tắt,
 * thông báo) sau khi bỏ vai trò điều phối viên riêng. Thực đơn mỗi ngày chỉ
 * chọn 1 nhà hàng, tick món có sẵn trong danh mục thay vì gõ tay từng ngày. */
export class AdminPage extends BasePage {
  constructor() {
    super();
    this.date = null;
    this.today = null;

    this.dashboard = new DashboardView({ onConfirmPayment: () => this.loadDashboard() });
    this.menuItemsList = new MenuItemsList({
      getRestaurants: () => this.restaurants.restaurants,
      getUser: () => this.user,
    });
    this.catalogManager = new CatalogManager("catalog-panel", {
      onChange: () => this.menuFromCatalog.loadCatalog(),
      getCanEdit: () => this.applyDateCanEdit,
    });
    this.menuFromCatalog = new MenuFromCatalog({
      getCanEdit: () => this.applyDateCanEdit,
      getOwnerName: () => this.applyDateOwnerName,
      onApplied: () => {
        this.loadDashboard();
        this.loadMenuItemsList();
        this.refreshApplyDateLock();
        this.refreshTodayLock();
      },
    });
    // this.restaurants dựng ở init() vì cần this.user (biết isAdmin) đã có
    this.applyDateCanEdit = true;
    this.applyDateOwnerName = null;
    this.datePicker = new DatePicker(
      "admin-date-picker",
      (date) => this.switchDate(date),
      null,
      (date) => this.clearDate(date)
    );
    this.paymentInfo = new PaymentInfoForm();
  }

  async init() {
    // Hiện/khoá "Gửi thông báo" và "Thông tin nhận tiền" tuỳ theo hôm nay ai
    // phụ trách — tính trong refreshTodayLock() vì cần gọi API round-status.
    Dom.byId("lock-orders-btn").addEventListener("click", () => this.lockOrders());
    Dom.byId("dashboard-refresh-btn").addEventListener("click", (e) => this.refresh(e));
    Dom.byId("broadcast-form").addEventListener("submit", (e) => this.sendBroadcast(e));
    Dom.byId("apply-date").addEventListener("change", () => {
      this.loadMenuItemsList();
      this.refreshApplyDateLock();
    });

    this.restaurants = new RestaurantManager({
      getCanEdit: () => this.applyDateCanEdit,
      getCanManage: () => this.user.is_admin,
      onManageCatalog: (restaurant) => this.catalogManager.open(restaurant),
    });
    await this.restaurants.load();
    await Promise.all([
      this.refreshApplyDateLock(),
      this.refreshTodayLock(),
      this.loadDashboard(),
      this.loadSummary(),
      this.loadMenuItemsList(),
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
        this.refreshTodayLock();
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
      },
      order_updated: () => {
        this.loadDashboard();
        this.loadSummary();
      },
      menu_updated: () => {
        this.loadMenuItemsList();
        this.refreshTodayLock();
      },
    });
  }

  /** Tải "Món đã thêm cho ngày này" theo đúng ngày đang chọn ở "Ngày áp dụng". */
  async loadMenuItemsList() {
    const date = Dom.byId("apply-date").value || Formatter.todayIso();
    await this.menuItemsList.load(date);
  }

  /** admin hoặc đang phụ trách đúng ngày ở "Ngày áp dụng" thì mới thao tác
   * được nhà hàng/danh mục/áp dụng thực đơn — gọi lại mỗi khi đổi ngày đó.
   * Gọi ngay ở init() nên khoá có hiệu lực từ lúc trang vừa tải, không phải
   * đợi người dùng tự bấm/chọn gì trước mới lộ ra là bị khoá. */
  async refreshApplyDateLock() {
    const date = Dom.byId("apply-date").value || Formatter.todayIso();
    const status = await this.fetchRoundStatus(date);
    this.applyDateOwnerName = status.owner ? status.owner.name : null;
    this.applyDateCanEdit =
      this.user.is_admin || !status.owner || status.owner.id === this.user.id;
    if (this.restaurants) this.restaurants.applyLock();
    if (this.catalogManager) this.catalogManager.render();
    if (this.menuFromCatalog) this.menuFromCatalog.applyLock();
  }

  /** "Gửi thông báo" và "Thông tin nhận tiền" không gắn với "Ngày áp dụng",
   * mà theo đúng người đang phụ trách VÒNG ĐẶT HIỆN TẠI (không hẳn là đúng
   * ngày dương lịch hôm nay — quá giờ chốt thì vòng hiện tại đã chuyển sang
   * ngày kế tiếp còn mở, giống hệt "Ngày áp dụng" mặc định ở mục 2):
   * - Thông tin nhận tiền: CHỈ hiện với chính chủ vòng hiện tại, kể cả admin
   *   cũng không thấy nếu không phải là người đang đứng ra đặt.
   * - Gửi thông báo: hiện cho admin (như trước) VÀ thêm cho chủ vòng hiện
   *   tại dù không phải admin; khoá (disable) nếu có người khác phụ trách. */
  async refreshTodayLock() {
    const currentRoundDate = await this.fetchCurrentRoundDate();
    const status = await this.fetchRoundStatus(currentRoundDate);
    const isOwner = Boolean(status.owner && status.owner.id === this.user.id);
    const canEdit = !status.owner || isOwner;

    const paymentSection = Dom.byId("payment-info-section");
    const paymentNote = Dom.byId("payment-locked-note");
    if (paymentSection) paymentSection.hidden = !isOwner;
    if (paymentNote) {
      paymentNote.hidden = isOwner;
      paymentNote.textContent = isOwner
        ? ""
        : status.owner
          ? `Thông tin nhận tiền chỉ hiện với người đang đứng ra đặt hôm nay — hiện là ${status.owner.name}.`
          : "Thông tin nhận tiền chỉ hiện khi bạn tự đứng ra đặt hôm nay (thêm món ở mục 2).";
    }

    const broadcastSection = Dom.byId("broadcast-section");
    const broadcastNote = Dom.byId("broadcast-locked-note");
    const canSeeBroadcast = this.user.is_admin || isOwner;
    if (broadcastSection) {
      broadcastSection.hidden = !canSeeBroadcast;
      if (canSeeBroadcast) {
        broadcastSection.querySelectorAll("input, textarea, button").forEach((el) => {
          el.disabled = !canEdit;
        });
      }
    }
    if (broadcastNote) {
      broadcastNote.hidden = canSeeBroadcast;
      broadcastNote.textContent = canSeeBroadcast
        ? ""
        : `Gửi thông báo chỉ dành cho admin hoặc người đang đứng ra đặt hôm nay — hiện là ${status.owner ? status.owner.name : "chưa ai"}.`;
    }
  }

  /** Ngày của vòng đặt đang mở theo giờ chốt — khớp CHÍNH XÁC với
   * Config.current_order_date() mà backend dùng để authorize broadcast/thông
   * tin nhận tiền (không dùng "default_date" vì cái đó còn phụ thuộc đã có
   * thực đơn ngày nào hay chưa, dễ lệch với backend khi ngày khác đã có
   * người dựng thực đơn trước trong khi hôm nay thì chưa). */
  async fetchCurrentRoundDate() {
    try {
      const data = await api.get("/menu/dates");
      return data.current_round_date || data.today || Formatter.todayIso();
    } catch (err) {
      return Formatter.todayIso();
    }
  }

  /** round-status của một ngày cụ thể — trả về "chưa ai nhận" nếu lỗi mạng thay vì ném lỗi lên UI. */
  async fetchRoundStatus(date) {
    if (!date) return { owner: null, is_open: false };
    try {
      return await api.get(`/orders/round-status?date=${encodeURIComponent(date)}`);
    } catch (err) {
      return { owner: null, is_open: false };
    }
  }

  /** admin hoặc đang phụ trách đúng ngày đang xem ở Bảng điều khiển thì mới
   * chốt đơn được (renderHeader() đã set disabled theo trạng thái đơn trước
   * đó — ở đây chỉ khoá thêm theo quyền, không mở lại nếu đơn đã chốt). */
  applyDashboardLock(status) {
    const button = Dom.byId("lock-orders-btn");
    if (!button || this.user.is_admin) return;
    const isOwner = Boolean(status.owner && status.owner.id === this.user.id);
    if (status.owner && !isOwner) button.disabled = true;
  }

  /** Tải + vẽ lại toàn bộ Bảng điều khiển cho this.date, cùng các khoá đi kèm (nút chốt đơn, nút xác nhận tiền). */
  async loadDashboard() {
    try {
      const query = this.date ? `?date=${encodeURIComponent(this.date)}` : "";
      const data = await api.get(`/admin/dashboard${query}`);

      this.date = data.date;
      this.today = data.today;
      this.renderDatePicker(data);
      const status = await this.fetchRoundStatus(this.date);
      this.dashboard.canConfirmPayment = Boolean(
        status.owner && status.owner.id === this.user.id
      );
      this.dashboard.render(data);
      this.applyDashboardLock(status);
      this.refreshTodayLock();
    } catch (err) {
      this.dashboard.showError(() => this.loadDashboard(), err.message);
    }
  }

  /** Dùng lại DatePicker của nhân viên, chỉ cần đưa về đúng dạng dữ liệu. */
  renderDatePicker(data) {
    const days = (data.available_dates || []).map((d) => ({
      date: d.date,
      item_count: 0,
      is_today: d.date === data.today,
      closed: false,
      has_order: false,
      // Chỉ admin hoặc đúng chủ ngày đó mới thấy dấu x gỡ ngày — người khác
      // bấm cũng bị backend chặn, nhưng ẩn hẳn cho đỡ hiểu nhầm là gỡ được.
      can_delete: this.user.is_admin || !d.owner_id || d.owner_id === this.user.id,
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

  /** Chuyển ngày đang xem ở Bảng điều khiển (khác với "Ngày áp dụng" ở mục 2). */
  async switchDate(date) {
    if (!date || date === this.date) return;
    this.date = date;
    await Promise.all([this.loadDashboard(), this.loadSummary()]);
  }

  /** Gỡ hẳn một ngày đã lỡ dựng (thực đơn + đơn) — không áp dụng cho hôm nay. */
  async clearDate(date) {
    if (!window.confirm(`Gỡ bỏ hẳn ngày ${date}? Toàn bộ thực đơn và đơn đã đặt của ngày này sẽ mất, không hoàn tác được.`)) {
      return;
    }
    try {
      await api.delete(`/admin/orders/day/${encodeURIComponent(date)}`);
      toasts.info("Đã gỡ ngày", date);
      if (this.date === date) this.date = null;
      if ((Dom.byId("apply-date").value || "") === date) {
        Dom.byId("apply-date").value = Formatter.todayIso();
        await Promise.all([this.loadMenuItemsList(), this.refreshApplyDateLock()]);
      }
      await Promise.all([this.loadDashboard(), this.loadSummary()]);
    } catch (err) {
      toasts.error("Không gỡ được ngày này", err.message);
    }
  }

  /** Nút "Làm mới" ở Bảng điều khiển — chỉ tải lại dashboard, không đụng mục 1/2. */
  async refresh(event) {
    const button = event.currentTarget;
    Dom.setBusy(button, true, "Đang làm mới");
    await this.loadDashboard();
    Dom.setBusy(button, false);
  }

  /** Chốt toàn bộ đơn pending của this.date rồi tự mở tab Grab cho từng quán có link. */
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

  // ===== Tóm tắt nhanh (gộp từ trang Gom đơn cũ) =====

  /** Đoạn tóm tắt AI ngắn cho this.date (số đơn, món/quán nổi bật). */
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

  // ===== Gửi thông báo (gộp từ trang Gom đơn cũ) =====

  /** Gửi thông báo nổi cho mọi người — nút chỉ hiện/khoá đúng theo refreshTodayLock(), route vẫn tự kiểm lại quyền. */
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
