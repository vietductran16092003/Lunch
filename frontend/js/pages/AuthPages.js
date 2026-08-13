import { GoogleSignIn } from "../components/GoogleSignIn.js";
import { PasswordToggle } from "../components/PasswordToggle.js";
import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { BasePage } from "./BasePage.js";

/** Khung chung cho các trang xác thực: không có thanh điều hướng. */
class AuthPage extends BasePage {
  static usesNavbar = false;

  constructor(formId, errorId) {
    super();
    this.form = Dom.byId(formId);
    this.errorBox = Dom.byId(errorId);
  }

  showError(message) {
    if (!this.errorBox) return;
    this.errorBox.textContent = message;
    this.errorBox.style.display = "block";
  }

  hideError() {
    if (this.errorBox) this.errorBox.style.display = "none";
  }

  /** Gán lỗi cho đúng ô nhập, trả về true nếu ô đó sai. */
  markField(inputId, errorId, message) {
    const input = Dom.byId(inputId);
    Dom.setText(errorId, message || "");
    if (input) {
      if (message) input.setAttribute("aria-invalid", "true");
      else input.removeAttribute("aria-invalid");
    }
    return Boolean(message);
  }

  focusFirstInvalid() {
    const first = this.form.querySelector("[aria-invalid='true']");
    if (first) first.focus();
  }
}

// ===================================================================

export class LoginPage extends AuthPage {
  constructor() {
    super("login-form", "login-error");
  }

  async init() {
    PasswordToggle.attachAll();

    const options = await api.get("/auth/options").catch(() => ({ google_enabled: false }));
    new GoogleSignIn(options, (msg) => this.showError(msg)).render();

    this.form.addEventListener("submit", (e) => this.submit(e));
  }

  async submit(event) {
    event.preventDefault();

    const email = Dom.byId("email");
    const password = Dom.byId("password");
    const button = this.form.querySelector("button[type='submit']");

    this.hideError();
    email.removeAttribute("aria-invalid");
    password.removeAttribute("aria-invalid");
    Dom.setBusy(button, true, "Đang đăng nhập");

    try {
      await api.post("/login", { email: email.value.trim(), password: password.value });
      window.location.href = "index.html";
    } catch (err) {
      this.showError(err.isNetworkError ? "Không kết nối được đến server, vui lòng thử lại" : err.message);
      email.setAttribute("aria-invalid", "true");
      password.setAttribute("aria-invalid", "true");
      email.focus();
      Dom.setBusy(button, false);
    }
  }
}

// ===================================================================

export class RegisterPage extends AuthPage {
  constructor() {
    super("register-form", "register-error");
    this.minPasswordLength = 8;
  }

  async init() {
    PasswordToggle.attachAll();

    const options = await api.get("/auth/options").catch(() => ({
      google_enabled: false,
      allowed_domains_label: "@fpt.com",
      min_password_length: 8,
    }));

    this.minPasswordLength = options.min_password_length || 8;
    const label = options.allowed_domains_label || "@fpt.com";

    Dom.setText("register-subtitle", `Dùng email nội bộ công ty (${label}) để đăng ký.`);
    Dom.setText("reg-email-help", `Chỉ chấp nhận email ${label}.`);
    Dom.setText("reg-password-help", `Ít nhất ${this.minPasswordLength} ký tự.`);

    new GoogleSignIn(options, (msg) => this.showError(msg)).render();
    this.form.addEventListener("submit", (e) => this.submit(e));
  }

  async submit(event) {
    event.preventDefault();
    this.hideError();

    const name = Dom.byId("reg-name").value.trim();
    const email = Dom.byId("reg-email").value.trim();
    const password = Dom.byId("reg-password").value;
    const password2 = Dom.byId("reg-password2").value;

    // Kiểm tra tại chỗ trước khi gọi server
    const invalid = [
      this.markField("reg-name", "reg-name-error", name ? "" : "Vui lòng nhập họ tên"),
      this.markField("reg-email", "reg-email-error", email ? "" : "Vui lòng nhập email"),
      this.markField(
        "reg-password", "reg-password-error",
        password.length >= this.minPasswordLength
          ? "" : `Mật khẩu phải có ít nhất ${this.minPasswordLength} ký tự`
      ),
      this.markField(
        "reg-password2", "reg-password2-error",
        password2 === password ? "" : "Hai mật khẩu chưa khớp nhau"
      ),
    ].some(Boolean);

    if (invalid) {
      this.focusFirstInvalid();
      return;
    }

    const button = this.form.querySelector("button[type='submit']");
    Dom.setBusy(button, true, "Đang tạo tài khoản");
    try {
      await api.post("/register", { name, email, password });
      window.location.href = "index.html";
    } catch (err) {
      this.showError(err.isNetworkError ? "Không kết nối được đến server" : err.message);
      // Lỗi từ server thường thuộc về email (trùng hoặc sai domain)
      if (err.status === 409 || /email/i.test(err.message)) {
        this.markField("reg-email", "reg-email-error", err.message);
        Dom.byId("reg-email").focus();
      }
      Dom.setBusy(button, false);
    }
  }
}

// ===================================================================

export class ForgotPasswordPage extends AuthPage {
  constructor() {
    super("forgot-form", null);
  }

  async init() {
    this.form.addEventListener("submit", (e) => this.submit(e));
  }

  async submit(event) {
    event.preventDefault();

    const box = Dom.byId("forgot-result");
    const button = this.form.querySelector("button[type='submit']");
    Dom.clear(box);
    Dom.setBusy(button, true, "Đang tạo link");

    try {
      const data = await api.post("/password/forgot", {
        email: Dom.byId("forgot-email").value.trim(),
      });

      box.appendChild(Dom.notice("info", null, data.message));
      this.form.hidden = true;
    } catch (err) {
      box.appendChild(Dom.notice("error", null, "Không kết nối được đến server"));
    } finally {
      Dom.setBusy(button, false);
    }
  }
}

// ===================================================================

export class ResetPasswordPage extends AuthPage {
  constructor() {
    super("reset-form", "reset-error");
    this.token = new URLSearchParams(window.location.search).get("token") || "";
  }

  async init() {
    PasswordToggle.attachAll();

    if (!this.token) {
      this.showError("Thiếu mã đặt lại mật khẩu. Hãy mở lại link từ trang Quên mật khẩu.");
      this.form.querySelector("button[type='submit']").disabled = true;
    }

    this.form.addEventListener("submit", (e) => this.submit(e));
  }

  async submit(event) {
    event.preventDefault();
    this.hideError();

    const password = Dom.byId("reset-password").value;
    const password2 = Dom.byId("reset-password2").value;

    const invalid = [
      this.markField(
        "reset-password", "reset-password-error",
        password.length >= 8 ? "" : "Mật khẩu phải có ít nhất 8 ký tự"
      ),
      this.markField(
        "reset-password2", "reset-password2-error",
        password2 === password ? "" : "Hai mật khẩu chưa khớp nhau"
      ),
    ].some(Boolean);

    if (invalid) {
      this.focusFirstInvalid();
      return;
    }

    const button = this.form.querySelector("button[type='submit']");
    Dom.setBusy(button, true, "Đang đổi mật khẩu");
    try {
      await api.post("/password/reset", { token: this.token, password });

      this.form.hidden = true;
      const box = Dom.byId("reset-result");
      Dom.clear(box).appendChild(
        Dom.notice("success", "Đã đổi mật khẩu", "Bạn có thể đăng nhập bằng mật khẩu mới.")
      );
    } catch (err) {
      this.showError(err.isNetworkError ? "Không kết nối được đến server" : err.message);
      Dom.setBusy(button, false);
    }
  }
}
