import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";
import { toasts } from "../core/ToastManager.js";
import { ImageUploadField } from "./ImageUploadField.js";

/** Form thêm món. Khóa cho tới khi chọn được nhà hàng. */
export class MenuForm {
  constructor({ onCreated } = {}) {
    this.form = Dom.byId("menu-form");
    this.onCreated = onCreated || (() => {});
    if (!this.form) return;

    this.select = Dom.byId("item-restaurant");
    this.submitBtn = Dom.byId("menu-submit-btn");
    this.dependentIds = [
      "item-name", "item-price", "item-date", "item-description", "item-image",
    ];

    this.image = new ImageUploadField({
      inputId: "item-image",
      previewId: "item-image-preview",
      emptyId: "item-image-empty",
      label: "ảnh",
    });

    const dateInput = Dom.byId("item-date");
    if (dateInput && !dateInput.value) dateInput.value = Formatter.todayIso();

    this.select.addEventListener("change", () => this.updateAvailability());
    this.form.addEventListener("submit", (e) => this.submit(e));
    this.updateAvailability();
  }

  updateAvailability(hasRestaurants = null) {
    if (!this.form) return;
    const chosen = Boolean(this.select.value);

    if (hasRestaurants !== null) this.select.disabled = !hasRestaurants;
    this.submitBtn.disabled = !chosen;
    this.submitBtn.title = chosen ? "" : "Chọn nhà hàng trước khi thêm món";

    this.dependentIds.forEach((id) => {
      const el = Dom.byId(id);
      if (el) el.disabled = !chosen;
    });
  }

  validate() {
    const name = Dom.byId("item-name");
    const price = Dom.byId("item-price");

    // Báo lỗi ngay dưới ô sai và đưa focus về đó
    const checks = [
      [this.select, "item-restaurant-error", !this.select.value, "Vui lòng chọn nhà hàng"],
      [name, "item-name-error", !name.value.trim(), "Vui lòng nhập tên món"],
      [price, "item-price-error", !price.value || Number(price.value) <= 0,
        "Giá phải lớn hơn 0"],
    ];

    let firstInvalid = null;
    checks.forEach(([el, errorId, invalid, text]) => {
      Dom.setText(errorId, invalid ? text : "");
      if (invalid) {
        el.setAttribute("aria-invalid", "true");
        if (!firstInvalid) firstInvalid = el;
      } else {
        el.removeAttribute("aria-invalid");
      }
    });

    if (firstInvalid) firstInvalid.focus();
    return !firstInvalid;
  }

  async submit(event) {
    event.preventDefault();
    if (!this.validate()) return;

    const message = Dom.byId("menu-form-message");
    const name = Dom.byId("item-name");

    Dom.setBusy(this.submitBtn, true, "Đang thêm món");
    try {
      await api.post("/admin/menu", {
        name: name.value.trim(),
        description: Dom.byId("item-description").value.trim(),
        price: parseFloat(Dom.byId("item-price").value),
        available_date: Dom.byId("item-date").value,
        restaurant_id: parseInt(this.select.value, 10),
        image_url: this.image.url,
      });

      message.className = "message-success";
      message.textContent = "Đã thêm món vào thực đơn";
      toasts.success("Đã thêm món", name.value.trim());

      // Giữ lại nhà hàng và ngày để thêm món tiếp cho nhanh
      name.value = "";
      Dom.byId("item-price").value = "";
      Dom.byId("item-description").value = "";
      this.image.reset();
      name.focus();

      await this.onCreated();
    } catch (err) {
      message.className = "message-error";
      message.textContent = err.message;
      toasts.error("Thêm món thất bại", err.message);
    } finally {
      Dom.setBusy(this.submitBtn, false);
    }
  }
}
