import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { hasAnyRole } from "../core/roles.js";

/** Thanh điều hướng dùng chung, tự tải người dùng hiện tại. */
export class Navbar {
  constructor(placeholderId = "navbar-placeholder") {
    this.placeholder = Dom.byId(placeholderId);
    this.user = null;
  }

  async render() {
    if (!this.placeholder) return null;

    this.placeholder.innerHTML = `
      <header class="navbar">
        <div class="brand"><span class="dot" aria-hidden="true"></span> Lunch App</div>
        <nav aria-label="Điều hướng chính">
          <a href="index.html">Thực đơn</a>
          <a href="history.html">Lịch sử</a>
        </nav>
        <div id="user-info">
          <span class="user-avatar" id="user-avatar" aria-hidden="true"></span>
          <span id="user-name"></span>
          <!-- Các link theo vai trò, ẩn mặc định cho tới khi biết user là ai -->
          <a href="coordinator.html" id="coordinator-link" hidden>Gom đơn</a>
          <a href="treasury.html" id="treasury-link" hidden>Quỹ</a>
          <a href="admin.html" id="admin-link" hidden>Trang quản trị</a>
          <a href="#" id="logout-link">Đăng xuất</a>
        </div>
      </header>
    `;

    this.highlightActive();
    Dom.byId("logout-link").addEventListener("click", (e) => this.logout(e));

    return this.loadCurrentUser();
  }

  highlightActive() {
    const current = window.location.pathname.split("/").pop() || "index.html";
    document.querySelectorAll(".navbar nav a, #user-info a[href]").forEach((link) => {
      if (link.getAttribute("href") === current) {
        link.classList.add("active");
        // Trình đọc màn hình biết đang ở trang nào, không chỉ dựa vào màu nền
        link.setAttribute("aria-current", "page");
      }
    });
  }

  async loadCurrentUser() {
    try {
      this.user = await api.get("/me");
      Dom.setText("user-name", this.user.name);
      this.renderAvatar(this.user);

      if (this.user.is_admin) Dom.byId("admin-link").hidden = false;
      // Admin thấy hết mọi link — vừa để tiện thao tác, vừa vì admin có đủ quyền
      // gọi mọi endpoint đứng sau các link đó.
      if (hasAnyRole(this.user, ["coordinator", "admin"])) {
        Dom.byId("coordinator-link").hidden = false;
      }
      if (hasAnyRole(this.user, ["treasurer", "admin"])) {
        Dom.byId("treasury-link").hidden = false;
      }

      return this.user;
    } catch (err) {
      window.location.href = "login.html";
      return null;
    }
  }

  /** Chưa có ảnh thật của nhân viên, nên hiện chữ cái đầu tên trên nền màu ổn
   * định theo tên — mỗi người luôn ra cùng một màu giữa các lần tải trang. */
  renderAvatar(user) {
    const avatar = Dom.byId("user-avatar");
    if (!avatar || !user) return;

    const initial = (user.name || "?").trim().charAt(0).toUpperCase();
    let hash = 0;
    for (const ch of user.email || user.name || "") hash = (hash * 31 + ch.charCodeAt(0)) % 360;

    avatar.textContent = initial;
    avatar.style.background = `hsl(${hash}, 55%, 88%)`;
    avatar.style.color = `hsl(${hash}, 55%, 30%)`;
  }

  async logout(event) {
    event.preventDefault();
    try {
      await api.post("/logout");
    } finally {
      window.location.href = "login.html";
    }
  }
}
