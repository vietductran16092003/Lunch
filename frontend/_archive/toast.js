// Hệ thống thông báo nổi (toast), dùng chung cho mọi trang.
// Vùng chứa là aria-live="polite" nên trình đọc màn hình đọc được nội dung mới
// mà không cướp focus của người đang thao tác.

const TOAST_ICONS = {
  success: "✓",
  error: "!",
  warning: "◬",
  info: "i",
};

const TOAST_DEFAULT_MS = 4500;

function getToastRegion() {
  let region = document.getElementById("toast-region");
  if (region) return region;

  region = document.createElement("div");
  region.id = "toast-region";
  region.className = "toast-region";
  region.setAttribute("role", "status");
  region.setAttribute("aria-live", "polite");
  region.setAttribute("aria-atomic", "false");
  document.body.appendChild(region);
  return region;
}

function dismissToast(toast) {
  if (!toast.isConnected || toast.classList.contains("is-leaving")) return;
  toast.classList.add("is-leaving");
  window.setTimeout(() => toast.remove(), 200);
}

/**
 * Hiện một thông báo nổi.
 * @param {string} title  Dòng tiêu đề ngắn
 * @param {object} options {body, type: success|error|warning|info, duration}
 */
function showToast(title, options = {}) {
  const { body = "", type = "info", duration = TOAST_DEFAULT_MS } = options;
  const region = getToastRegion();

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;

  const icon = document.createElement("span");
  icon.className = "toast-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = TOAST_ICONS[type] || TOAST_ICONS.info;

  const text = document.createElement("div");
  text.className = "toast-text";

  const titleEl = document.createElement("div");
  titleEl.className = "toast-title";
  titleEl.textContent = title;
  text.appendChild(titleEl);

  if (body) {
    const bodyEl = document.createElement("div");
    bodyEl.className = "toast-body";
    bodyEl.textContent = body;
    text.appendChild(bodyEl);
  }

  const close = document.createElement("button");
  close.type = "button";
  close.className = "toast-close";
  close.setAttribute("aria-label", "Đóng thông báo");
  close.textContent = "×";
  close.addEventListener("click", () => dismissToast(toast));

  toast.append(icon, text, close);
  region.appendChild(toast);

  // Giữ tối đa 4 thông báo cùng lúc để không che mất nội dung trang
  while (region.children.length > 4) {
    region.firstElementChild.remove();
  }

  if (duration > 0) {
    const timer = window.setTimeout(() => dismissToast(toast), duration);
    // Dừng đếm ngược khi người dùng đang đọc
    toast.addEventListener("mouseenter", () => window.clearTimeout(timer));
    toast.addEventListener("focusin", () => window.clearTimeout(timer));
  }

  return toast;
}

window.showToast = showToast;
