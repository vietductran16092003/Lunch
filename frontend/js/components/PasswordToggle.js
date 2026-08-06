import { Dom } from "../core/Dom.js";

const EYE_OPEN = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
  stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12Z"/>
  <circle cx="12" cy="12" r="2.8"/></svg>`;

const EYE_OFF = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
  stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M2 12s3.6-6.5 10-6.5c1.6 0 3 .4 4.3 1"/>
  <path d="M21.2 8.7c.5.6.8 1.1.8 1.3 0 0-3.6 6.5-10 6.5-1 0-1.9-.15-2.7-.4"/>
  <path d="M9.6 9.9a2.8 2.8 0 0 0 3.9 3.9"/>
  <path d="m3 3 18 18"/></svg>`;

/** Nút con mắt hiện/ẩn mật khẩu, nằm gọn bên phải trong khung nhập. */
export class PasswordToggle {
  constructor(input) {
    this.input = input;
  }

  attach() {
    const { input } = this;
    if (!input || input.dataset.toggleAttached) return this;
    input.dataset.toggleAttached = "1";

    const wrap = Dom.el("span", { class: "password-wrap" });
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);

    this.button = Dom.el("button", {
      type: "button",
      class: "password-toggle",
      html: EYE_OPEN,
      "aria-label": "Hiện mật khẩu",
      "aria-pressed": "false",
    });
    this.button.addEventListener("click", () => this.toggle());
    wrap.appendChild(this.button);

    return this;
  }

  toggle() {
    const showing = this.input.type === "text";
    this.input.type = showing ? "password" : "text";
    this.button.innerHTML = showing ? EYE_OPEN : EYE_OFF;
    this.button.setAttribute("aria-label", showing ? "Hiện mật khẩu" : "Ẩn mật khẩu");
    this.button.setAttribute("aria-pressed", String(!showing));

    // Giữ con trỏ ở cuối ô để người dùng gõ tiếp được ngay
    this.input.focus();
    const end = this.input.value.length;
    try {
      this.input.setSelectionRange(end, end);
    } catch (err) {
      /* vài loại input không hỗ trợ setSelectionRange */
    }
  }

  /** Gắn cho mọi ô mật khẩu trên trang. */
  static attachAll(root = document) {
    root.querySelectorAll("input[type='password']").forEach((input) => {
      new PasswordToggle(input).attach();
    });
  }
}
