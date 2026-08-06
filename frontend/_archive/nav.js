// Thanh điều hướng dùng chung cho mọi trang (trừ login.html)
function renderNavbar() {
  const placeholder = document.getElementById("navbar-placeholder");
  if (!placeholder) return;

  placeholder.innerHTML = `
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

  loadCurrentUser();
  highlightActiveNavLink();

  document.getElementById("logout-link").addEventListener("click", async function (e) {
    e.preventDefault();
    await fetch(`${API_BASE}/logout`, { method: "POST", credentials: "include" });
    window.location.href = "login.html";
  });
}

function highlightActiveNavLink() {
  const currentPage = window.location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".navbar nav a, .navbar #admin-link").forEach((link) => {
    if (link.getAttribute("href") === currentPage) {
      link.classList.add("active");
      // Trình đọc màn hình biết đang ở trang nào, không chỉ dựa vào màu nền
      link.setAttribute("aria-current", "page");
    }
  });
}

async function loadCurrentUser() {
  try {
    const res = await fetch(`${API_BASE}/me`, { credentials: "include" });
    if (!res.ok) {
      window.location.href = "login.html";
      return;
    }
    const user = await res.json();
    document.getElementById("user-name").textContent = user.name;
    if (user.is_admin) {
      document.getElementById("admin-link").hidden = false;
    }
  } catch (err) {
    window.location.href = "login.html";
  }
}

renderNavbar();
