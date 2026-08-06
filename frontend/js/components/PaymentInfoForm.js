import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { toasts } from "../core/ToastManager.js";
import { ImageUploadField } from "./ImageUploadField.js";

/** Thông tin nhận tiền của người đứng ra đặt: số liên hệ và mã QR. */
export class PaymentInfoForm {
  constructor() {
    this.form = Dom.byId("payment-info-form");
    if (!this.form) return;

    this.qr = new ImageUploadField({
      inputId: "admin-qr-file",
      previewId: "qr-preview-img",
      emptyId: "qr-preview-empty",
      label: "ảnh QR",
    });

    this.form.addEventListener("submit", (e) => this.submit(e));
    this.load();
  }

  async load() {
    try {
      const data = await api.get("/payment-info");
      Dom.byId("admin-phone").value = data.phone || "";
      this.qr.setUrl(data.qr_image_url || null);
    } catch (err) {
      this.qr.setUrl(null);
    }
  }

  async submit(event) {
    event.preventDefault();
    const message = Dom.byId("payment-info-message");
    const button = this.form.querySelector("button[type='submit']");

    Dom.setBusy(button, true, "Đang lưu");
    try {
      await api.put("/admin/payment-info", {
        phone: Dom.byId("admin-phone").value.trim(),
        qr_image_url: this.qr.url || "",
      });
      message.className = "message-success";
      message.textContent = "Đã lưu thông tin thanh toán";
      toasts.success("Đã lưu thông tin nhận tiền");
    } catch (err) {
      message.className = "message-error";
      message.textContent = err.message;
    } finally {
      Dom.setBusy(button, false);
    }
  }
}
