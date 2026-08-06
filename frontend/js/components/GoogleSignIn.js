import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";

/**
 * Nút "Đăng nhập bằng Google".
 * Chưa cấu hình GOOGLE_CLIENT_ID thì cả khối tự ẩn, phần đăng nhập bằng mật
 * khẩu vẫn dùng bình thường.
 */
export class GoogleSignIn {
  static SCRIPT_URL = "https://accounts.google.com/gsi/client";

  constructor(options, onError, { blockId = "google-block", wrapId = "google-signin-wrap" } = {}) {
    this.options = options;
    this.onError = onError || (() => {});
    this.block = Dom.byId(blockId);
    this.wrapId = wrapId;
  }

  render() {
    if (!this.block) return;

    if (!this.options.google_enabled) {
      this.block.hidden = true;
      return;
    }

    const script = Dom.el("script", { src: GoogleSignIn.SCRIPT_URL, async: true, defer: true });
    script.onerror = () => { this.block.hidden = true; };
    script.onload = () => this.initialise();
    document.head.appendChild(script);
  }

  initialise() {
    if (!window.google || !window.google.accounts) {
      this.block.hidden = true;
      return;
    }

    window.google.accounts.id.initialize({
      client_id: this.options.google_client_id,
      callback: (response) => this.handleCredential(response),
    });

    window.google.accounts.id.renderButton(Dom.byId(this.wrapId), {
      theme: "outline",
      size: "large",
      shape: "pill",
      text: "signin_with",
      locale: "vi",
      width: 320,
    });

    this.block.hidden = false;
  }

  async handleCredential(response) {
    try {
      await api.post("/auth/google", { credential: response.credential });
      window.location.href = "index.html";
    } catch (err) {
      this.onError(err.message);
    }
  }
}
