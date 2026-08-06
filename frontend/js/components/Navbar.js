import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";

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
          <span id="user-name"></span>
          <!-- Link quản trị nằm ngoài thanh điều hướng chính, chỉ admin mới thấy -->
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
    document.querySelectorAll(".navbar nav a, .navbar #admin-link").forEach((link) => {
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
      if (this.user.is_admin) Dom.byId("admin-link").hidden = false;
      return this.user;
    } catch (err) {
      window.location.href = "login.html";
      return null;
    }
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
