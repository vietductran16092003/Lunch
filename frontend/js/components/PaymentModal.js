import { ApiClient, api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";
import { toasts } from "../core/ToastManager.js";

/**
 * Hộp thoại chuyển khoản.
 * Chỉ còn hình thức chuyển khoản: hiện liên hệ + mã QR của người đặt, nhân viên
 * bấm báo đã chuyển rồi đóng lại chờ người đặt xác nhận.
 */
export class PaymentModal {
  constructor({ onPaid } = {}) {
    this.overlay = Dom.byId("payment-modal-overlay");
    this.onPaid = onPaid || (() => {});
    this.paymentInfo = null;
    this.order = null;
    this.lastFocused = null;

    if (this.overlay) this.bind();
  }

  bind() {
    Dom.byId("payment-confirm-btn").addEventListener("click", () => this.declarePayment());
    Dom.byId("payment-success-close").addEventListener("click", () => this.close());
    Dom.byId("payment-modal-cancel").addEventListener("click", () => this.close());

    this.overlay.addEventListener("click", (e) => {
      if (e.target === this.overlay) this.close();
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.overlay.style.display === "flex") this.close();
    });
  }

  async open(order) {
    if (!this.overlay) return;
    this.order = order;
    this.lastFocused = document.activeElement;

    this.overlay.hidden = false;
    this.overlay.style.display = "flex";
    this.setStep("choose");
    Dom.setText("payment-modal-message", "");

    this.renderSummary();
    await this.loadPaymentInfo();
    this.renderPaymentInfo();

    const confirmBtn = Dom.byId("payment-confirm-btn");
    if (confirmBtn) confirmBtn.focus();
  }

  close() {
    if (!this.overlay) return;
    this.overlay.style.display = "none";
    this.overlay.hidden = true;
    if (this.lastFocused) this.lastFocused.focus();
  }

  setStep(step) {
    Dom.byId("payment-step-choose").hidden = step !== "choose";
    Dom.byId("payment-step-success").hidden = step !== "success";
  }

  async loadPaymentInfo() {
    // Không cache giữa các lần mở: mỗi đơn có thể thuộc một ngày khác nhau,
    // và mỗi ngày có thể do một người khác đứng ra đặt/thu tiền.
    const date = this.order ? this.order.order_date : "";
    try {
      this.paymentInfo = await api.get(`/payment-info?date=${encodeURIComponent(date)}`);
    } catch (err) {
      this.paymentInfo = { name: null, phone: null, qr_image_url: null };
    }
    return this.paymentInfo;
  }

  get collectorName() {
    return (this.paymentInfo && this.paymentInfo.name) || "người đặt";
  }

  renderSummary() {
    const panel = Dom.byId("order-summary-panel");
    if (!panel) return;
    Dom.clear(panel);

    const items = this.order ? this.order.items : [];
    if (!items.length) {
      panel.appendChild(
        Dom.el("p", { class: "subtitle", style: "margin:0;", text: "Chưa có món nào được chọn." })
      );
      return;
    }

    const list = Dom.el("ul", { style: "margin:0; padding-left:18px;" });
    items.forEach((i) => {
      list.appendChild(
        Dom.el("li", {
          text: `${i.name} × ${i.quantity} — ${Formatter.money(i.price * i.quantity)}`,
        })
      );
    });

    const total = items.reduce((sum, i) => sum + i.price * i.quantity, 0);
    panel.appendChild(
      Dom.el(
        "div",
        { class: "card", style: "margin:0;" },
        list,
        Dom.el("p", {
          style: "margin:8px 0 0; font-weight:600;",
          text: `Thành tiền: ${Formatter.money(total)}`,
        })
      )
    );
  }

  renderPaymentInfo() {
    const panel = Dom.byId("payment-info-panel");
    if (!panel || !this.paymentInfo) return;
    Dom.clear(panel);

    const contact = Dom.el(
      "div",
      { class: "card", style: "margin:0;" },
      Dom.el("div", { class: "preview-box" },
        Dom.el("p", { class: "preview-label", text: "Chuyển khoản cho:" }),
        Dom.el("p", { class: "preview-name", text: this.collectorName }),
        this.paymentInfo.phone
          ? Dom.el("p", { class: "preview-phone mono", text: this.paymentInfo.phone })
          : Dom.el("p", { class: "preview-phone", text: "Chưa có số liên hệ." })
      )
    );

    const qrBox = Dom.el("div", { class: "card", style: "margin:0; text-align:center;" });
    if (this.paymentInfo.qr_image_url) {
      qrBox.append(
        Dom.el("p", {
          class: "subtitle",
          style: "margin:0 0 8px;",
          text: "Quét mã để chuyển khoản:",
        }),
        Dom.el("img", {
          class: "qr-frame",
          src: ApiClient.assetUrl(this.paymentInfo.qr_image_url),
          alt: `Mã QR chuyển khoản của ${this.collectorName}`,
        })
      );
    } else {
      qrBox.textContent = "Người đặt chưa cập nhật mã QR chuyển khoản.";
    }

    panel.append(contact, qrBox);
  }

  async declarePayment() {
    const message = Dom.byId("payment-modal-message");
    const button = Dom.byId("payment-confirm-btn");

    if (!this.order) {
      message.className = "message-error";
      message.textContent = "Bạn chưa có đơn nào hôm nay để thanh toán.";
      return;
    }
    if (this.order.status === "pending") {
      message.className = "message-error";
      message.textContent = "Đơn chưa được chốt, chờ người đặt chốt đơn đã nhé.";
      return;
    }

    Dom.setBusy(button, true, "Đang gửi báo chuyển khoản");
    try {
      const result = await api.post(`/orders/${this.order.id}/pay`);
      const order = result.order;

      Dom.setText("pay-success-amount", Formatter.money(order.total_cost));
      Dom.setText(
        "pay-success-meta",
        `Đơn #${order.id} · đang chờ ${this.collectorName} xác nhận đã nhận tiền`
      );
      this.setStep("success");
      Dom.byId("payment-success-close").focus();

      toasts.info(
        "Đã báo chuyển khoản",
        `Chờ ${this.collectorName} xác nhận đã nhận ${Formatter.money(order.total_cost)}`
      );
      await this.onPaid();
    } catch (err) {
      message.className = "message-error";
      message.textContent = err.message;
    } finally {
      Dom.setBusy(button, false);
    }
  }
}
