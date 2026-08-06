import { Dom } from "./Dom.js";

const ICONS = { success: "✓", error: "!", warning: "◬", info: "i" };

/**
 * Thông báo nổi.
 * Vùng chứa là aria-live="polite" nên trình đọc màn hình đọc được nội dung mới
 * mà không cướp focus của người đang thao tác.
 */
export class ToastManager {
  static DEFAULT_DURATION = 4500;
  static MAX_VISIBLE = 4;

  constructor() {
    this.region = null;
  }

  ensureRegion() {
    if (this.region && this.region.isConnected) return this.region;

    this.region = Dom.byId("toast-region") || Dom.el("div", {
      id: "toast-region",
      class: "toast-region",
      role: "status",
      "aria-live": "polite",
      "aria-atomic": "false",
    });

    if (!this.region.isConnected) document.body.appendChild(this.region);
    return this.region;
  }

  show(title, { body = "", type = "info", duration = ToastManager.DEFAULT_DURATION } = {}) {
    const region = this.ensureRegion();

    const close = Dom.el("button", {
      type: "button",
      class: "toast-close",
      "aria-label": "Đóng thông báo",
      text: "×",
    });

    const toast = Dom.el(
      "div",
      { class: `toast ${type}` },
      Dom.el("span", { class: "toast-icon", "aria-hidden": "true", text: ICONS[type] || ICONS.info }),
      Dom.el(
        "div",
        { class: "toast-text" },
        Dom.el("div", { class: "toast-title", text: title }),
        body ? Dom.el("div", { class: "toast-body", text: body }) : null
      ),
      close
    );

    close.addEventListener("click", () => this.dismiss(toast));
    region.appendChild(toast);

    // Giữ tối đa vài thông báo để không che mất nội dung trang
    while (region.children.length > ToastManager.MAX_VISIBLE) {
      region.firstElementChild.remove();
    }

    if (duration > 0) {
      const timer = window.setTimeout(() => this.dismiss(toast), duration);
      // Dừng đếm ngược khi người dùng đang đọc
      toast.addEventListener("mouseenter", () => window.clearTimeout(timer));
      toast.addEventListener("focusin", () => window.clearTimeout(timer));
    }

    return toast;
  }

  dismiss(toast) {
    if (!toast.isConnected || toast.classList.contains("is-leaving")) return;
    toast.classList.add("is-leaving");
    window.setTimeout(() => toast.remove(), 200);
  }

  success(title, body) { return this.show(title, { body, type: "success" }); }
  error(title, body) { return this.show(title, { body, type: "error" }); }
  warning(title, body) { return this.show(title, { body, type: "warning" }); }
  info(title, body) { return this.show(title, { body, type: "info" }); }
}

export const toasts = new ToastManager();
