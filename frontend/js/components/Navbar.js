import { NotificationBell } from "./NotificationBell.js";
import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { hasAnyRole } from "../core/roles.js";
import { Theme } from "../core/theme.js";

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
        <a href="index.html" class="brand"><span class="dot" aria-hidden="true"></span> Lunch App</a>
        <div class="navbar-right">
          <nav aria-label="Điều hướng chính">
            <a href="index.html"><span class="nav-icon" aria-hidden="true">🍱</span>Thực đơn</a>
            <a href="history.html"><span class="nav-icon" aria-hidden="true">🕘</span>Lịch sử</a>
          </nav>
          <div id="notification-bell" class="notification-bell"></div>
          <div id="user-info" class="user-menu">
            <button type="button" class="user-menu-trigger" id="user-menu-trigger"
                    aria-haspopup="true" aria-expanded="false">
              <span class="user-avatar" id="user-avatar" aria-hidden="true"></span>
              <span id="user-name"></span>
              <span class="user-menu-caret" aria-hidden="true">▾</span>
            </button>
            <div class="user-menu-dropdown" id="user-menu-dropdown">
              <!-- Các link theo vai trò, ẩn mặc định cho tới khi biết user là ai -->
              <a href="treasury.html" id="treasury-link" hidden><span class="nav-icon" aria-hidden="true">💰</span>Quỹ</a>
              <a href="admin.html" id="admin-link" hidden><span class="nav-icon" aria-hidden="true">🛵</span>Đặt hàng chung</a>
              <a href="settings.html" id="settings-link" hidden><span class="nav-icon" aria-hidden="true">⚙️</span>Cài đặt hệ thống</a>
              <button type="button" id="theme-toggle-btn" class="user-menu-action"></button>
              <a href="#" id="logout-link"><span class="nav-icon" aria-hidden="true">🚪</span>Đăng xuất</a>
            </div>
          </div>
        </div>
      </header>
    `;

    this.highlightActive();
    Dom.byId("logout-link").addEventListener("click", (e) => this.logout(e));
    this.bindUserMenu();
    this.bindThemeToggle();

    return this.loadCurrentUser();
  }

  bindThemeToggle() {
    const button = Dom.byId("theme-toggle-btn");
    if (!button) return;

    const render = () => {
      const isDark = Theme.get() === "dark";
      button.innerHTML = "";
      button.append(
        Dom.el("span", { class: "nav-icon", "aria-hidden": "true", text: isDark ? "☀️" : "🌙" }),
        document.createTextNode(isDark ? "Giao diện sáng" : "Giao diện tối")
      );
    };
    render();

    button.addEventListener("click", () => {
      Theme.toggle();
      render();
    });
  }

  /** Trỏ chuột vào là mở (CSS :hover), nhưng vẫn bấm/gõ phím dùng được cho
   * màn cảm ứng và bàn phím — không chỉ dựa vào hover. */
  bindUserMenu() {
    const menu = Dom.byId("user-info");
    const trigger = Dom.byId("user-menu-trigger");
    if (!menu || !trigger) return;

    const close = () => {
      menu.classList.remove("is-open");
      trigger.setAttribute("aria-expanded", "false");
    };

    trigger.addEventListener("click", () => {
      const open = menu.classList.toggle("is-open");
      trigger.setAttribute("aria-expanded", String(open));
    });

    document.addEventListener("click", (e) => {
      if (!menu.contains(e.target)) close();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") close();
    });
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

      // Ai cũng có thể đứng ra đặt hàng cho một ngày (không cố định ở admin
      // nữa), nên mọi người đã đăng nhập đều thấy link này — không khoá link
      // dù ngày khác đã có người phụ trách, vì họ vẫn chọn ngày khác được.
      Dom.byId("admin-link").hidden = false;

      if (hasAnyRole(this.user, ["treasurer", "admin"])) {
        Dom.byId("treasury-link").hidden = false;
      } else {
        Dom.byId("treasury-link").remove();
      }

      if (hasAnyRole(this.user, ["admin"])) {
        Dom.byId("settings-link").hidden = false;
      } else {
        Dom.byId("settings-link").remove();
      }

      new NotificationBell().mount();

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
