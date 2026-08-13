import { DatePicker } from "../components/DatePicker.js";
import { MenuGrid } from "../components/MenuGrid.js";
import { OrderStepper } from "../components/OrderStepper.js";
import { PaymentModal } from "../components/PaymentModal.js";
import { ApiClient, api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";
import { toasts } from "../core/ToastManager.js";
import { BasePage } from "./BasePage.js";

/** Trang thực đơn của nhân viên. */
export class MenuPage extends BasePage {
  constructor() {
    super();
    this.selectedDate = null;
    this.today = null;
    this.availableDates = [];
    this.order = null;
    this.cutoffLabel = "11:00";
    this.cutoffPassed = false;

    this.stepper = new OrderStepper();
    this.grid = new MenuGrid("menu-list", (selection) => this.renderSelectionTotals(selection));
    this.datePicker = new DatePicker("date-picker", (date) => this.switchDate(date), "date-picker-title");
    this.modal = new PaymentModal({ onPaid: () => this.loadOrder() });
  }

  async init() {
    this.stepper.render(0);
    this.grid.showLoading();

    Dom.byId("place-order-btn").addEventListener("click", () => this.placeOrder());
    Dom.byId("payment-method-btn").addEventListener("click", () => this.modal.open(this.order));
    Dom.byId("menu-search").addEventListener("input", (e) => this.grid.filter(e.target.value));
    Dom.byId("menu-search").addEventListener("keydown", (e) => {
      if (e.key === "Enter") this.grid.filter(e.target.value);
    });
    Dom.byId("menu-search-btn").addEventListener("click", () => {
      this.grid.filter(Dom.byId("menu-search").value);
    });

    await this.loadDates();
    await Promise.all([this.loadMenu(), this.loadOrder(), this.loadSuggestions()]);

    this.listen({
      orders_locked: (data) => {
        // Chỉ báo khi đúng ngày đang xem bị chốt
        if (!data.date || data.date === this.selectedDate) {
          toasts.info("Đơn đã được chốt", "Người đặt đang đặt trên Grab.");
        }
        this.refreshAll();
      },
      orders_ordered: () => {
        toasts.success("Quán đã nhận đơn", "Đến lúc chuyển khoản rồi.");
        this.loadOrder();
      },
      payment_confirmed: () => {
        // Chỉ báo cho đúng người vừa được xác nhận
        if (this.order && this.order.awaiting_confirmation) {
          toasts.success("Người đặt đã xác nhận nhận tiền");
        }
        this.loadOrder();
      },
      // Quản trị viên lên thực đơn ngày mới thì dải chọn ngày phải hiện thêm
      menu_updated: () => this.refreshAll(),
    });
  }

  async refreshAll() {
    await this.loadDates();
    await Promise.all([this.loadMenu(), this.loadOrder(), this.loadSuggestions()]);
  }

  /** Gợi ý món dựa trên lịch sử đặt của chính người dùng (Phase 3). */
  async loadSuggestions() {
    const box = Dom.byId("suggestions-box");
    if (!box) return;
    try {
      const query = this.selectedDate ? `?date=${encodeURIComponent(this.selectedDate)}` : "";
      const data = await api.get(`/ai/suggestions${query}`);
      Dom.clear(box);
      if (!data.suggestions || !data.suggestions.length) return;

      const cards = data.suggestions.map((item) => {
        const card = Dom.el(
          "button",
          { type: "button", class: "suggestion-card", "aria-label": `Thêm ${item.name}` },
          item.image_url
            ? Dom.el("img", {
                class: "suggestion-thumb",
                src: ApiClient.assetUrl(item.image_url),
                alt: "",
                loading: "lazy",
              })
            : Dom.el("div", { class: "suggestion-thumb is-placeholder", "aria-hidden": "true", text: "🍽️" }),
          Dom.el(
            "div",
            { class: "suggestion-info" },
            Dom.el("span", { class: "suggestion-name", text: item.name }),
            Dom.el("span", { class: "suggestion-meta", text: `${Formatter.money(item.price)} · đã đặt ${item.order_count} lần` })
          ),
          Dom.el("span", { class: "suggestion-add", "aria-hidden": "true", text: "+" })
        );
        card.addEventListener("click", () => {
          this.grid.addQuantity(item.id, 1);
          const input = Dom.byId(`qty-${item.id}`);
          if (input) input.scrollIntoView({ behavior: "smooth", block: "center" });
        });
        return card;
      });

      box.appendChild(
        Dom.el(
          "div",
          { class: "suggestions-panel" },
          Dom.el("span", { class: "section-title", text: "🍀 Gợi ý cho bạn" }),
          Dom.el("div", { class: "suggestions-row" }, ...cards)
        )
      );
    } catch (err) {
      Dom.clear(box);
    }
  }

  // ===== Tải dữ liệu =====

  /** Danh sách ngày có thực đơn + ngày mặc định để chọn (hôm nay, hoặc mai nếu đã quá giờ chốt). */
  async loadDates() {
    try {
      const data = await api.get("/menu/dates");
      this.today = data.today;
      this.availableDates = data.dates || [];
      this.cutoffLabel = data.cutoff || this.cutoffLabel;
      if (!this.selectedDate) this.selectedDate = data.default_date || data.today;
    } catch (err) {
      this.availableDates = [];
      if (!this.selectedDate) this.selectedDate = Formatter.todayIso();
      if (!this.today) this.today = this.selectedDate;
    }
    this.datePicker.render(this.availableDates, this.selectedDate, this.today);
  }

  /** Tải danh sách món của this.selectedDate và vẽ lại toàn bộ tiêu đề/lưới món. */
  async loadMenu() {
    try {
      const query = this.selectedDate ? `?date=${encodeURIComponent(this.selectedDate)}` : "";
      const data = await api.get(`/menu${query}`);

      this.cutoffLabel = data.cutoff || this.cutoffLabel;
      this.cutoffPassed = Boolean(data.cutoff_passed);
      this.selectedDate = data.date;
      if (!this.today && data.is_today) this.today = data.date;

      const dayName = Formatter.dayLabel(data.date, this.today).toLowerCase();
      Dom.setText(
        "menu-heading-title",
        data.is_today ? "Thực đơn hôm nay" : `Thực đơn ${dayName}`
      );
      Dom.setText(
        "today-date",
        `Ngày ${data.date} · ${data.items.length} món · giờ chốt đơn ${this.cutoffLabel}`
      );
      Dom.setText(
        "my-order-heading",
        data.is_today ? "Đơn hàng của tôi hôm nay" : `Đơn hàng của tôi ${dayName}`
      );

      this.renderCutoffNotice();
      this.grid.render(data.items, { locked: this.cutoffPassed });
      this.grid.filter(Dom.byId("menu-search").value);
      await this.loadOwnerStatus();
    } catch (err) {
      this.grid.showError("Không tải được thực đơn. Kiểm tra kết nối rồi tải lại trang.");
    }
  }

  /** Tên người đang đứng ra đặt chung/thu tiền cho ngày đang xem. */
  async loadOwnerStatus() {
    const el = Dom.byId("order-owner-info");
    if (!el || !this.selectedDate) return;
    try {
      const status = await api.get(
        `/orders/round-status?date=${encodeURIComponent(this.selectedDate)}`
      );
      el.classList.remove("is-you", "is-unclaimed");
      if (!status.owner) {
        el.classList.add("is-unclaimed");
        el.textContent = "Chưa có ai đứng ra đặt chung cho ngày này.";
      } else if (this.user && status.owner.id === this.user.id) {
        el.classList.add("is-you");
        el.textContent = "Bạn đang đứng ra đặt chung cho ngày này.";
      } else {
        el.textContent = `${status.owner.name} đang đứng ra đặt chung cho ngày này.`;
      }
    } catch (err) {
      el.textContent = "";
    }
  }

  /** Đơn hiện tại của chính người dùng cho this.selectedDate. */
  async loadOrder() {
    const box = Dom.byId("my-order");
    if (!box) return;

    try {
      const query = this.selectedDate ? `?date=${encodeURIComponent(this.selectedDate)}` : "";
      const data = await api.get(`/orders/my${query}`);

      this.order = data.order;
      this.cutoffLabel = data.cutoff || this.cutoffLabel;
      this.cutoffPassed = Boolean(data.cutoff_passed);

      this.stepper.render(this.order ? this.order.step_index : 0);
      this.renderOrderCard(box, data);
    } catch (err) {
      Dom.clear(box).appendChild(Dom.emptyState("⚠️", "Không tải được đơn hàng."));
    }
  }

  /** Đổi ngày đang xem (chọn hôm nay hay đặt trước hôm sau) và tải lại mọi phần liên quan. */
  async switchDate(date) {
    if (!date || date === this.selectedDate) return;
    this.selectedDate = date;
    this.datePicker.render(this.availableDates, this.selectedDate, this.today);
    await Promise.all([this.loadMenu(), this.loadOrder(), this.loadSuggestions()]);
  }

  // ===== Hiển thị =====

  renderSelectionTotals(selection) {
    const total = selection.reduce((sum, i) => sum + i.price * i.quantity, 0);
    const count = selection.reduce((sum, i) => sum + i.quantity, 0);

    Dom.setText("selection-total", Formatter.money(total));
    Dom.setText(
      "selection-count",
      count === 0 ? "Chưa chọn món nào" : `${count} phần · ${selection.length} món`
    );
  }

  renderCutoffNotice() {
    const box = Dom.byId("cutoff-notice");
    if (!box) return;
    Dom.clear(box);

    if (!this.cutoffPassed) {
      // Đặt trước cho ngày sau: nói rõ để nhân viên biết đang đặt cho hôm nào
      if (this.selectedDate && this.selectedDate !== this.today) {
        const dayName = Formatter.dayLabel(this.selectedDate, this.today).toLowerCase();
        box.appendChild(
          Dom.notice(
            "info",
            `Bạn đang đặt trước cho ${dayName} (${Formatter.shortDate(this.selectedDate)})`,
            `Đơn sẽ được chốt lúc ${this.cutoffLabel} ngày hôm đó. ` +
              "Từ giờ tới lúc đó bạn vẫn sửa hoặc hủy được."
          )
        );
      }
      return;
    }

    // Đã quá giờ: nếu có thực đơn ngày sau thì mời đặt trước thay vì báo cụt
    const nextOpen = this.availableDates.find((d) => !d.closed);
    let extra = null;
    let body = "Hôm nay không đặt hoặc sửa đơn được nữa. Hẹn bạn sáng mai nhé.";

    if (nextOpen) {
      const dayName = Formatter.dayLabel(nextOpen.date, this.today).toLowerCase();
      body =
        `Ngày ${Formatter.shortDate(this.selectedDate)} không đặt được nữa, ` +
        `nhưng bạn đặt trước cho ${dayName} được rồi.`;

      const button = Dom.el("button", {
        type: "button",
        class: "subtle",
        text: `Đặt trước cho ${dayName} (${Formatter.shortDate(nextOpen.date)})`,
      });
      button.addEventListener("click", () => this.switchDate(nextOpen.date));
      extra = Dom.el("div", { style: "margin-top:8px;" }, button);
    }

    box.appendChild(
      Dom.notice("warning", `Đã quá giờ chốt đơn (${this.cutoffLabel})`, body, extra)
    );
  }

  renderOrderCard(box, data) {
    Dom.clear(box);

    if (!this.order) {
      const when = data.is_today
        ? "hôm nay"
        : Formatter.dayLabel(data.date, this.today).toLowerCase();
      box.appendChild(Dom.emptyState("🧾", `Bạn chưa đặt món ${when}.`));
      this.updatePaymentButton();
      return;
    }

    const list = Dom.el("ul", { style: "margin:0; padding-left:18px;" });
    this.order.items.forEach((item) => {
      list.appendChild(
        Dom.el(
          "li",
          {},
          `${item.name} × ${item.quantity} — ${Formatter.money(item.price * item.quantity)}`,
          item.note
            ? Dom.el("span", { class: "item-note", text: ` (${item.note})` })
            : null
        )
      );
    });

    const totalLine =
      this.order.shipping_share > 0
        ? Dom.el(
            "div",
            { style: "text-align:right;" },
            Dom.el("strong", { class: "mono", text: Formatter.money(this.order.total_cost) }),
            Dom.el("div", {
              class: "subtitle",
              style: "margin:0;",
              text: `gồm ${Formatter.money(this.order.shipping_share)} tiền ship`,
            })
          )
        : Dom.el("strong", { class: "mono", text: Formatter.money(this.order.total_cost) });

    box.append(
      Dom.el(
        "div",
        { class: "card-head" },
        Dom.el("span", {
          class: `badge ${this.order.status}`,
          text: this.order.status_label,
        }),
        totalLine
      ),
      list,
      Dom.el("p", {
        class: "subtitle",
        style: "margin:8px 0 0;",
        text: this.order.payment_method === "fund"
          ? "Thanh toán: Trả bằng quỹ chung"
          : "Thanh toán: Chuyển khoản cho người đặt",
      })
    );

    if (this.order.status === "pending" && !this.cutoffPassed) {
      box.appendChild(this.buildCancelButton());
    }

    const paidByFund = this.order.payment_method === "fund";

    if (this.order.status === "ordered" && !this.order.paid_at && !paidByFund) {
      box.appendChild(
        Dom.notice("warning", "Quán đã nhận đơn", "Đến lúc chuyển khoản cho người đặt.")
      );
    }
    if (this.order.awaiting_confirmation && !paidByFund) {
      box.appendChild(
        Dom.notice("info", "Đã báo chuyển khoản", "Đang chờ người đặt xác nhận đã nhận tiền.")
      );
    }
    if (this.order.status === "completed") {
      box.appendChild(
        paidByFund
          ? Dom.notice(
              "success",
              "Đã thanh toán bằng quỹ chung",
              "Thủ quỹ đã trả tiền quán bằng quỹ, bạn không cần chuyển khoản."
            )
          : Dom.notice(
              "success",
              "Người đặt đã xác nhận nhận tiền",
              "Xong rồi, bạn không cần làm gì thêm."
            )
      );
    }

    this.updatePaymentButton();
  }

  buildCancelButton() {
    const cancel = Dom.el("button", {
      class: "danger",
      type: "button",
      style: "margin-top:12px;",
      text: "Hủy đơn",
    });

    cancel.addEventListener("click", async () => {
      if (!window.confirm("Hủy đơn của bạn?")) return;
      Dom.setBusy(cancel, true, "Đang hủy đơn");
      try {
        await api.delete(`/orders/${this.order.id}`);
        toasts.info("Đã hủy đơn");
        await this.loadOrder();
        await this.loadDates();
      } catch (err) {
        Dom.setBusy(cancel, false);
        toasts.error("Không hủy được đơn", err.message);
      }
    });

    return cancel;
  }

  /** Nút chỉ sáng khi thật sự còn phải trả tiền. */
  updatePaymentButton() {
    const button = Dom.byId("payment-method-btn");
    if (!button) return;

    const paidByFund = this.order && this.order.payment_method === "fund";
    button.hidden = Boolean(paidByFund);
    if (paidByFund) return;

    // Chưa có đơn nào thì chưa có gì để thanh toán — khoá nút lại
    button.disabled = !this.order;

    const needsPayment =
      this.order && this.order.status === "ordered" && !this.order.paid_at;
    button.classList.toggle("lit", Boolean(needsPayment));
    button.textContent =
      this.order && this.order.paid_at ? "Xem thanh toán" : "Chuyển khoản";
  }

  // ===== Đặt món =====

  /** Gửi đơn mới (hoặc ghi đè đơn pending cũ) cho this.selectedDate từ các món đã chọn trong lưới. */
  async placeOrder() {
    const button = Dom.byId("place-order-btn");
    const message = Dom.byId("order-message");
    const selection = this.grid.getSelection();

    if (!selection.length) {
      message.className = "message-error";
      message.textContent = "Vui lòng chọn ít nhất một món";
      this.grid.focusFirstInput();
      return;
    }

    Dom.setBusy(button, true, "Đang gửi đơn");
    try {
      await api.post("/orders", {
        items: selection.map((i) => ({
          menu_item_id: i.menu_item_id,
          quantity: i.quantity,
          note: i.note || undefined,
        })),
        order_date: this.selectedDate,
      });

      const forDay =
        this.selectedDate === this.today
          ? "hôm nay"
          : Formatter.dayLabel(this.selectedDate, this.today).toLowerCase();
      const total = selection.reduce((s, i) => s + i.price * i.quantity, 0);

      message.className = "message-success";
      message.textContent = `Đã gửi đơn cho ${forDay}`;
      toasts.success(
        this.selectedDate === this.today ? "Đặt món thành công" : "Đã đặt trước thành công",
        `${forDay} · ${selection.length} món · ${Formatter.money(total)}`
      );

      await Promise.all([this.loadOrder(), this.loadDates()]);
    } catch (err) {
      message.className = "message-error";
      message.textContent = err.message;
      toasts.error("Đặt món thất bại", err.message);
    } finally {
      Dom.setBusy(button, false);
    }
  }
}
