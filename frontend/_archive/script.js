// Logic từng trang của Lunch App.
// Mỗi khối bên dưới tự kiểm tra phần tử gốc có tồn tại không, nên một file dùng
// được cho mọi trang mà không chạy nhầm code của trang khác.

// ===== Tiện ích dùng chung =====

const money = (value) => `${Number(value || 0).toLocaleString("vi-VN")} đ`;

/** Chuyển đường dẫn tương đối do backend trả về thành URL đầy đủ. */
function assetUrl(path) {
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE.replace(/\/api$/, "")}${path}`;
}

/** Đặt text an toàn, tránh chèn HTML từ dữ liệu người dùng. */
function setText(el, text) {
  if (el) el.textContent = text;
}

function setBusy(button, busy, busyLabel) {
  if (!button) return;
  if (busy) {
    button.dataset.originalLabel = button.textContent;
    button.classList.add("is-busy");
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    if (busyLabel) button.setAttribute("aria-label", busyLabel);
  } else {
    button.classList.remove("is-busy");
    button.disabled = false;
    button.removeAttribute("aria-busy");
    button.removeAttribute("aria-label");
    if (button.dataset.originalLabel) button.textContent = button.dataset.originalLabel;
  }
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...options,
  });
  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }
  if (!response.ok) {
    const error = new Error((data && data.error) || "Yêu cầu không thành công");
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

async function apiJson(path, method, body) {
  return apiRequest(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
}

async function uploadImage(file) {
  const form = new FormData();
  form.append("file", file);
  return apiRequest("/admin/uploads", { method: "POST", body: form });
}

function statusBadgeClass(status) {
  return ["pending", "closed", "ordered", "completed"].includes(status) ? status : "pending";
}

// ===================================================================
//  CÁC TRANG XÁC THỰC
// ===================================================================

const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const forgotForm = document.getElementById("forgot-form");
const resetForm = document.getElementById("reset-form");

// Mọi ô mật khẩu trên các trang này đều có nút hiện/ẩn
if (loginForm || registerForm || resetForm) {
  attachAllPasswordToggles();
}

function showFieldError(inputId, errorId, text) {
  const input = document.getElementById(inputId);
  const error = document.getElementById(errorId);
  setText(error, text || "");
  if (input) {
    if (text) input.setAttribute("aria-invalid", "true");
    else input.removeAttribute("aria-invalid");
  }
  return Boolean(text);
}

// ----- Đăng nhập -----

if (loginForm) {
  (async () => {
    const options = await loadAuthOptions();
    setupGoogleSignIn(options, (message) => {
      const errorBox = document.getElementById("login-error");
      errorBox.textContent = message;
      errorBox.style.display = "block";
    });
  })();

  loginForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const emailInput = document.getElementById("email");
    const passwordInput = document.getElementById("password");
    const errorBox = document.getElementById("login-error");
    const submitBtn = loginForm.querySelector("button[type='submit']");

    errorBox.style.display = "none";
    emailInput.removeAttribute("aria-invalid");
    passwordInput.removeAttribute("aria-invalid");
    setBusy(submitBtn, true, "Đang đăng nhập");

    try {
      await apiJson("/login", "POST", {
        email: emailInput.value.trim(),
        password: passwordInput.value,
      });
      window.location.href = "index.html";
    } catch (err) {
      errorBox.textContent = err.status
        ? err.message
        : "Không kết nối được đến server, vui lòng thử lại";
      errorBox.style.display = "block";
      emailInput.setAttribute("aria-invalid", "true");
      passwordInput.setAttribute("aria-invalid", "true");
      emailInput.focus();
      setBusy(submitBtn, false);
    }
  });
}

// ----- Đăng ký -----

if (registerForm) {
  let minPasswordLength = 8;

  (async () => {
    const options = await loadAuthOptions();
    minPasswordLength = options.min_password_length || 8;
    const label = options.allowed_domains_label || "@fpt.com";
    setText(document.getElementById("register-subtitle"),
      `Dùng email nội bộ công ty (${label}) để đăng ký.`);
    setText(document.getElementById("reg-email-help"), `Chỉ chấp nhận email ${label}.`);
    setText(document.getElementById("reg-password-help"), `Ít nhất ${minPasswordLength} ký tự.`);
    setupGoogleSignIn(options, (message) => {
      const errorBox = document.getElementById("register-error");
      errorBox.textContent = message;
      errorBox.style.display = "block";
    });
  })();

  registerForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const errorBox = document.getElementById("register-error");
    const submitBtn = registerForm.querySelector("button[type='submit']");
    errorBox.style.display = "none";

    const name = document.getElementById("reg-name").value.trim();
    const email = document.getElementById("reg-email").value.trim();
    const password = document.getElementById("reg-password").value;
    const password2 = document.getElementById("reg-password2").value;

    // Kiểm tra tại chỗ trước khi gọi server, lỗi hiện ngay dưới đúng ô sai
    const invalid = [
      showFieldError("reg-name", "reg-name-error", name ? "" : "Vui lòng nhập họ tên"),
      showFieldError("reg-email", "reg-email-error", email ? "" : "Vui lòng nhập email"),
      showFieldError("reg-password", "reg-password-error",
        password.length >= minPasswordLength ? "" : `Mật khẩu phải có ít nhất ${minPasswordLength} ký tự`),
      showFieldError("reg-password2", "reg-password2-error",
        password2 === password ? "" : "Hai mật khẩu chưa khớp nhau"),
    ].some(Boolean);

    if (invalid) {
      const first = registerForm.querySelector("[aria-invalid='true']");
      if (first) first.focus();
      return;
    }

    setBusy(submitBtn, true, "Đang tạo tài khoản");
    try {
      await apiJson("/register", "POST", { name, email, password });
      window.location.href = "index.html";
    } catch (err) {
      errorBox.textContent = err.status ? err.message : "Không kết nối được đến server";
      errorBox.style.display = "block";
      // Lỗi từ server thường thuộc về email (trùng hoặc sai domain)
      if (err.status === 409 || /email/i.test(err.message)) {
        showFieldError("reg-email", "reg-email-error", err.message);
        document.getElementById("reg-email").focus();
      }
      setBusy(submitBtn, false);
    }
  });
}

// ----- Quên mật khẩu -----

if (forgotForm) {
  forgotForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const box = document.getElementById("forgot-result");
    const submitBtn = forgotForm.querySelector("button[type='submit']");
    box.innerHTML = "";

    setBusy(submitBtn, true, "Đang tạo link");
    try {
      const data = await apiJson("/password/forgot", "POST", {
        email: document.getElementById("forgot-email").value.trim(),
      });

      const notice = document.createElement("div");
      notice.className = "notice info";
      notice.style.marginTop = "16px";
      const body = document.createElement("div");
      body.textContent = data.message;
      notice.appendChild(body);
      box.appendChild(notice);

      // Chưa cấu hình gửi email nên hiện thẳng link cho môi trường nội bộ
      if (data.reset_token) {
        const url = new URL("reset-password.html", window.location.href);
        url.searchParams.set("token", data.reset_token);

        const linkBox = document.createElement("div");
        linkBox.className = "reset-link-box";
        const label = document.createElement("p");
        label.style.margin = "0 0 8px";
        label.textContent = `Link có hiệu lực trong ${data.ttl_minutes} phút:`;
        const anchor = document.createElement("a");
        anchor.href = url.toString();
        anchor.textContent = "Đặt lại mật khẩu ngay";
        linkBox.append(label, anchor);
        box.appendChild(linkBox);
      }
    } catch (err) {
      const notice = document.createElement("div");
      notice.className = "notice error";
      notice.style.marginTop = "16px";
      notice.textContent = "Không kết nối được đến server";
      box.appendChild(notice);
    } finally {
      setBusy(submitBtn, false);
    }
  });
}

// ----- Đặt lại mật khẩu -----

if (resetForm) {
  const token = new URLSearchParams(window.location.search).get("token") || "";

  if (!token) {
    const errorBox = document.getElementById("reset-error");
    errorBox.textContent = "Thiếu mã đặt lại mật khẩu. Hãy mở lại link từ trang Quên mật khẩu.";
    errorBox.style.display = "block";
    resetForm.querySelector("button[type='submit']").disabled = true;
  }

  resetForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const errorBox = document.getElementById("reset-error");
    const submitBtn = resetForm.querySelector("button[type='submit']");
    errorBox.style.display = "none";

    const password = document.getElementById("reset-password").value;
    const password2 = document.getElementById("reset-password2").value;

    const invalid = [
      showFieldError("reset-password", "reset-password-error",
        password.length >= 8 ? "" : "Mật khẩu phải có ít nhất 8 ký tự"),
      showFieldError("reset-password2", "reset-password2-error",
        password2 === password ? "" : "Hai mật khẩu chưa khớp nhau"),
    ].some(Boolean);

    if (invalid) {
      resetForm.querySelector("[aria-invalid='true']").focus();
      return;
    }

    setBusy(submitBtn, true, "Đang đổi mật khẩu");
    try {
      await apiJson("/password/reset", "POST", { token, password });

      resetForm.hidden = true;
      const box = document.getElementById("reset-result");
      box.innerHTML = "";
      const notice = document.createElement("div");
      notice.className = "notice success";
      notice.innerHTML =
        "<div><strong>Đã đổi mật khẩu</strong>Bạn có thể đăng nhập bằng mật khẩu mới.</div>";
      box.appendChild(notice);
    } catch (err) {
      errorBox.textContent = err.status ? err.message : "Không kết nối được đến server";
      errorBox.style.display = "block";
      setBusy(submitBtn, false);
    }
  });
}

// ===================================================================
//  TRANG THỰC ĐƠN CỦA NHÂN VIÊN
// ===================================================================

const menuList = document.getElementById("menu-list");

let menuItems = [];
let myOrder = null;
let cutoffLabel = "10:30";
let cutoffPassed = false;
let adminPaymentInfo = null;

// Ngày đang xem. Nếu quản trị viên đã lên thực đơn hôm sau thì nhân viên chọn
// được ngày đó và đặt trước, không phải chờ tới sáng hôm sau.
let selectedDate = null;
let todayIso = null;
let availableDates = [];

const WEEKDAY_LABELS = ["Chủ nhật", "Thứ hai", "Thứ ba", "Thứ tư", "Thứ năm", "Thứ sáu", "Thứ bảy"];

function dayLabel(iso) {
  if (!iso) return "";
  if (iso === todayIso) return "Hôm nay";
  const parsed = new Date(`${iso}T00:00:00`);
  const today = new Date(`${todayIso}T00:00:00`);
  const diffDays = Math.round((parsed - today) / 86400000);
  if (diffDays === 1) return "Ngày mai";
  return WEEKDAY_LABELS[parsed.getDay()] || iso;
}

function shortDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}`;
}

const STEP_DEFS = [
  { key: "pending", label: "Chọn món", hint: "Đặt trước giờ chốt" },
  { key: "closed", label: "Đã chốt đơn", hint: "Không sửa được nữa" },
  { key: "ordered", label: "Đặt trên Grab", hint: "Chờ quán xác nhận" },
  { key: "completed", label: "Hoàn tất", hint: "Đã thanh toán" },
];

function renderStepper() {
  const stepper = document.getElementById("order-stepper");
  if (!stepper) return;

  // Chưa đặt gì thì bước 1 là bước đang diễn ra
  const currentIndex = myOrder ? myOrder.step_index : 0;

  stepper.innerHTML = "";
  STEP_DEFS.forEach((step, index) => {
    const done = index < currentIndex;
    const current = index === currentIndex;

    const li = document.createElement("li");
    li.className = `step${done ? " is-done" : ""}${current ? " is-current" : ""}`;
    if (current) li.setAttribute("aria-current", "step");

    const track = document.createElement("div");
    track.className = "step-track";
    track.appendChild(document.createElement("span"));

    const body = document.createElement("div");
    body.className = "step-body";

    const mark = document.createElement("span");
    mark.className = "step-mark";
    mark.setAttribute("aria-hidden", "true");
    mark.textContent = done ? "✓" : String(index + 1);

    const text = document.createElement("div");
    const label = document.createElement("div");
    label.className = "step-label";
    label.textContent = `${index + 1}. ${step.label}`;
    const hint = document.createElement("div");
    hint.className = "step-hint";
    hint.textContent = done ? "Xong" : step.hint;
    text.append(label, hint);

    body.append(mark, text);
    li.append(track, body);

    // Trình đọc màn hình nghe được trạng thái, không chỉ nhìn thấy màu
    const state = done ? "đã xong" : current ? "đang thực hiện" : "chưa tới";
    const sr = document.createElement("span");
    sr.className = "sr-only";
    sr.textContent = `Bước ${index + 1}: ${step.label} — ${state}.`;
    li.appendChild(sr);

    stepper.appendChild(li);
  });
}

function renderCutoffNotice() {
  const box = document.getElementById("cutoff-notice");
  if (!box) return;
  box.innerHTML = "";

  if (!cutoffPassed) {
    // Đặt trước cho ngày sau: nói rõ để nhân viên biết mình đang đặt cho hôm nào
    if (selectedDate && selectedDate !== todayIso) {
      const notice = document.createElement("div");
      notice.className = "notice info";
      notice.setAttribute("role", "status");
      const body = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = `Bạn đang đặt trước cho ${dayLabel(selectedDate).toLowerCase()} (${shortDate(selectedDate)})`;
      body.appendChild(title);
      body.append(`Đơn sẽ được chốt lúc ${cutoffLabel} ngày hôm đó. Từ giờ tới lúc đó bạn vẫn sửa hoặc hủy được.`);
      notice.appendChild(body);
      box.appendChild(notice);
    }
    return;
  }

  const notice = document.createElement("div");
  notice.className = "notice warning";
  notice.setAttribute("role", "status");
  const body = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = `Đã quá giờ chốt đơn (${cutoffLabel})`;
  body.appendChild(title);

  // Nếu đã có thực đơn ngày sau thì mời họ đặt trước thay vì báo cụt
  const nextOpen = availableDates.find((d) => !d.closed);
  if (nextOpen) {
    body.append(`Ngày ${shortDate(selectedDate)} không đặt được nữa, nhưng bạn đặt trước cho ${dayLabel(nextOpen.date).toLowerCase()} được rồi.`);
    const action = document.createElement("div");
    action.style.marginTop = "8px";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "subtle";
    btn.textContent = `Đặt trước cho ${dayLabel(nextOpen.date).toLowerCase()} (${shortDate(nextOpen.date)})`;
    btn.addEventListener("click", () => switchDate(nextOpen.date));
    action.appendChild(btn);
    body.appendChild(action);
  } else {
    body.append("Hôm nay không đặt hoặc sửa đơn được nữa. Hẹn bạn sáng mai nhé.");
  }

  notice.appendChild(body);
  box.appendChild(notice);
}

/** Vẽ dải chọn ngày. Chỉ hiện khi có từ 2 ngày trở lên để đỡ rối. */
function renderDatePicker() {
  const picker = document.getElementById("date-picker");
  if (!picker) return;

  if (availableDates.length < 2) {
    picker.hidden = true;
    picker.innerHTML = "";
    return;
  }

  picker.hidden = false;
  picker.innerHTML = "";

  availableDates.forEach((entry) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = `date-chip${entry.closed ? " is-closed" : ""}`;
    chip.setAttribute("aria-pressed", String(entry.date === selectedDate));

    const day = document.createElement("span");
    day.className = "chip-day";
    day.textContent = `${dayLabel(entry.date)} · ${shortDate(entry.date)}`;

    const meta = document.createElement("span");
    meta.className = "chip-meta";
    meta.textContent = entry.closed
      ? `Đã chốt · ${entry.item_count} món`
      : `${entry.item_count} món`;

    chip.append(day, meta);

    if (entry.has_order) {
      const flag = document.createElement("span");
      flag.className = "chip-flag";
      flag.textContent = "✓ ĐÃ ĐẶT";
      chip.appendChild(flag);
    }

    const state = entry.closed ? "đã quá giờ chốt" : "còn đặt được";
    chip.setAttribute(
      "aria-label",
      `${dayLabel(entry.date)} ${shortDate(entry.date)}, ${entry.item_count} món, ${state}` +
        (entry.has_order ? ", bạn đã đặt" : "")
    );

    chip.addEventListener("click", () => switchDate(entry.date));
    picker.appendChild(chip);
  });
}

async function switchDate(date) {
  if (!date || date === selectedDate) return;
  selectedDate = date;
  renderDatePicker();
  await Promise.all([loadMenu(), loadMyOrder()]);
}

async function loadAvailableDates() {
  try {
    const data = await apiRequest("/menu/dates");
    todayIso = data.today;
    availableDates = data.dates || [];
    cutoffLabel = data.cutoff || cutoffLabel;
    if (!selectedDate) {
      selectedDate = data.default_date || data.today;
    }
  } catch (err) {
    availableDates = [];
    if (!selectedDate) selectedDate = new Date().toISOString().slice(0, 10);
    if (!todayIso) todayIso = selectedDate;
  }
  renderDatePicker();
}

function currentSelection() {
  const selected = [];
  document.querySelectorAll(".quantity-input").forEach((input) => {
    const quantity = parseInt(input.value, 10) || 0;
    if (quantity > 0) {
      const item = menuItems.find((m) => m.id === parseInt(input.dataset.id, 10));
      if (item) {
        selected.push({
          menu_item_id: item.id,
          name: item.name,
          price: item.price,
          quantity,
        });
      }
    }
  });
  return selected;
}

function refreshSelectionTotals() {
  const selection = currentSelection();
  const total = selection.reduce((sum, i) => sum + i.price * i.quantity, 0);
  const count = selection.reduce((sum, i) => sum + i.quantity, 0);

  setText(document.getElementById("selection-total"), money(total));
  setText(
    document.getElementById("selection-count"),
    count === 0 ? "Chưa chọn món nào" : `${count} phần · ${selection.length} món`
  );

  document.querySelectorAll(".menu-item").forEach((card) => {
    const input = card.querySelector(".quantity-input");
    card.classList.toggle("is-selected", (parseInt(input.value, 10) || 0) > 0);
  });
}

function buildMenuCard(item) {
  const card = document.createElement("article");
  card.className = "menu-item";
  card.dataset.id = item.id;

  if (item.image_url) {
    const img = document.createElement("img");
    img.className = "thumb";
    img.src = assetUrl(item.image_url);
    img.alt = `Ảnh món ${item.name}`;
    img.loading = "lazy";
    img.width = 320;
    img.height = 200;
    card.appendChild(img);
  } else {
    const placeholder = document.createElement("div");
    placeholder.className = "thumb-placeholder";
    placeholder.setAttribute("aria-hidden", "true");
    placeholder.textContent = "Chưa có ảnh";
    card.appendChild(placeholder);
  }

  const heading = document.createElement("h3");
  heading.id = `item-${item.id}-name`;
  heading.textContent = item.name;
  card.appendChild(heading);

  const price = document.createElement("div");
  price.className = "price";
  price.textContent = money(item.price);
  card.appendChild(price);

  if (item.description) {
    const desc = document.createElement("p");
    desc.textContent = item.description;
    card.appendChild(desc);
  }

  if (item.restaurant_name) {
    const line = document.createElement("div");
    line.className = "restaurant-line";
    line.textContent = item.restaurant_name;
    if (item.restaurant_rating) {
      const rating = document.createElement("span");
      rating.textContent = `· ${Number(item.restaurant_rating).toFixed(1)}/5 trên Grab`;
      line.appendChild(rating);
    }
    card.appendChild(line);
  }

  // Bộ đếm số lượng: nút to, có nhãn cho trình đọc màn hình
  const qty = document.createElement("div");
  qty.className = "qty";

  const label = document.createElement("label");
  label.setAttribute("for", `qty-${item.id}`);
  label.textContent = "Số lượng";

  const control = document.createElement("div");
  control.className = "qty-control";

  const minus = document.createElement("button");
  minus.type = "button";
  minus.textContent = "−";
  minus.setAttribute("aria-label", `Bớt một phần ${item.name}`);

  const input = document.createElement("input");
  input.type = "number";
  input.id = `qty-${item.id}`;
  input.className = "quantity-input";
  input.min = "0";
  input.max = "20";
  input.value = "0";
  input.inputMode = "numeric";
  input.dataset.id = item.id;
  input.setAttribute("aria-describedby", `item-${item.id}-name`);

  const plus = document.createElement("button");
  plus.type = "button";
  plus.textContent = "+";
  plus.setAttribute("aria-label", `Thêm một phần ${item.name}`);

  const step = (delta) => {
    const next = Math.min(20, Math.max(0, (parseInt(input.value, 10) || 0) + delta));
    input.value = String(next);
    minus.disabled = next === 0;
    refreshSelectionTotals();
  };

  minus.disabled = true;
  minus.addEventListener("click", () => step(-1));
  plus.addEventListener("click", () => step(1));
  input.addEventListener("input", () => {
    const value = Math.min(20, Math.max(0, parseInt(input.value, 10) || 0));
    input.value = String(value);
    minus.disabled = value === 0;
    refreshSelectionTotals();
  });

  control.append(minus, input, plus);
  qty.append(label, control);
  card.appendChild(qty);

  if (cutoffPassed) {
    [minus, plus, input].forEach((el) => { el.disabled = true; });
  }

  return card;
}

function renderMenu() {
  if (!menuList) return;
  menuList.setAttribute("aria-busy", "false");
  menuList.innerHTML = "";

  if (menuItems.length === 0) {
    menuList.innerHTML =
      '<div class="empty-state"><div class="icon" aria-hidden="true">🍽️</div>' +
      "Hôm nay chưa có thực đơn. Quản trị viên sẽ cập nhật sớm.</div>";
    return;
  }

  const fragment = document.createDocumentFragment();
  menuItems.forEach((item) => fragment.appendChild(buildMenuCard(item)));
  menuList.appendChild(fragment);
  refreshSelectionTotals();
}

async function loadMenu() {
  if (!menuList) return;
  try {
    const query = selectedDate ? `?date=${encodeURIComponent(selectedDate)}` : "";
    const data = await apiRequest(`/menu${query}`);
    menuItems = data.items || [];
    cutoffLabel = data.cutoff || cutoffLabel;
    cutoffPassed = Boolean(data.cutoff_passed);
    selectedDate = data.date;
    if (!todayIso && data.is_today) todayIso = data.date;

    setText(
      document.getElementById("menu-heading-title"),
      data.is_today ? "Thực đơn hôm nay" : `Thực đơn ${dayLabel(data.date).toLowerCase()}`
    );
    setText(
      document.getElementById("today-date"),
      `Ngày ${data.date} · ${menuItems.length} món · giờ chốt đơn ${cutoffLabel}`
    );
    setText(
      document.getElementById("my-order-heading"),
      data.is_today ? "Đơn hàng của tôi hôm nay" : `Đơn hàng của tôi ${dayLabel(data.date).toLowerCase()}`
    );
    renderCutoffNotice();
    renderMenu();
  } catch (err) {
    menuList.setAttribute("aria-busy", "false");
    menuList.innerHTML =
      '<div class="empty-state"><div class="icon" aria-hidden="true">⚠️</div>' +
      "Không tải được thực đơn. Kiểm tra kết nối rồi tải lại trang.</div>";
  }
}

async function loadMyOrder() {
  const box = document.getElementById("my-order");
  if (!box) return;

  try {
    const query = selectedDate ? `?date=${encodeURIComponent(selectedDate)}` : "";
    const data = await apiRequest(`/orders/my${query}`);
    myOrder = data.order;
    cutoffLabel = data.cutoff || cutoffLabel;
    cutoffPassed = Boolean(data.cutoff_passed);

    renderStepper();
    box.innerHTML = "";

    if (!myOrder) {
      const when = data.is_today ? "hôm nay" : dayLabel(data.date).toLowerCase();
      box.innerHTML =
        '<div class="empty-state"><div class="icon" aria-hidden="true">🧾</div>' +
        `Bạn chưa đặt món ${when}.</div>`;
      const payBtn = document.getElementById("payment-method-btn");
      if (payBtn) payBtn.classList.remove("lit");
      return;
    }

    const head = document.createElement("div");
    head.className = "card-head";
    const badge = document.createElement("span");
    badge.className = `badge ${statusBadgeClass(myOrder.status)}`;
    badge.textContent = myOrder.status_label;
    const total = document.createElement("strong");
    total.className = "mono";
    total.textContent = money(myOrder.total_cost);
    head.append(badge, total);
    box.appendChild(head);

    const list = document.createElement("ul");
    list.style.margin = "0";
    list.style.paddingLeft = "18px";
    myOrder.items.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = `${item.name} × ${item.quantity} — ${money(item.price * item.quantity)}`;
      list.appendChild(li);
    });
    box.appendChild(list);

    const payment = document.createElement("p");
    payment.className = "subtitle";
    payment.style.margin = "8px 0 0";
    payment.textContent = "Thanh toán: Chuyển khoản cho người đặt";
    box.appendChild(payment);

    if (myOrder.status === "pending" && !cutoffPassed) {
      const cancel = document.createElement("button");
      cancel.className = "danger";
      cancel.type = "button";
      cancel.style.marginTop = "12px";
      cancel.textContent = "Hủy đơn";
      cancel.addEventListener("click", async () => {
        if (!window.confirm("Hủy đơn hôm nay của bạn?")) return;
        setBusy(cancel, true, "Đang hủy đơn");
        try {
          await apiRequest(`/orders/${myOrder.id}`, { method: "DELETE" });
          showToast("Đã hủy đơn", { type: "info" });
          await Promise.all([loadMyOrder(), loadAvailableDates()]);
        } catch (err) {
          setBusy(cancel, false);
          showToast("Không hủy được đơn", { body: err.message, type: "error" });
        }
      });
      box.appendChild(cancel);
    }

    if (myOrder.status === "ordered" && !myOrder.paid_at) {
      const notice = document.createElement("div");
      notice.className = "notice warning";
      notice.style.marginTop = "12px";
      notice.innerHTML =
        "<div><strong>Quán đã nhận đơn</strong>Đến lúc chuyển khoản cho người đặt.</div>";
      box.appendChild(notice);
    }

    if (myOrder.awaiting_confirmation) {
      const notice = document.createElement("div");
      notice.className = "notice info";
      notice.style.marginTop = "12px";
      notice.innerHTML =
        "<div><strong>Đã báo chuyển khoản</strong>Đang chờ người đặt xác nhận đã nhận tiền.</div>";
      box.appendChild(notice);
    }

    if (myOrder.status === "completed") {
      const notice = document.createElement("div");
      notice.className = "notice success";
      notice.style.marginTop = "12px";
      notice.innerHTML =
        "<div><strong>Người đặt đã xác nhận nhận tiền</strong>Xong rồi, bạn không cần làm gì thêm.</div>";
      box.appendChild(notice);
    }

    // Nút chỉ sáng khi thật sự còn phải trả tiền: đã chốt đơn và chưa báo chuyển khoản
    const payBtn = document.getElementById("payment-method-btn");
    if (payBtn) {
      const needsPayment = myOrder.status === "ordered" && !myOrder.paid_at;
      payBtn.classList.toggle("lit", needsPayment);
      payBtn.textContent = myOrder.paid_at ? "Xem thanh toán" : "Chuyển khoản";
    }
  } catch (err) {
    box.innerHTML =
      '<div class="empty-state"><div class="icon" aria-hidden="true">⚠️</div>' +
      "Không tải được đơn hàng.</div>";
  }
}

// ----- Đặt món -----

const placeOrderBtn = document.getElementById("place-order-btn");
if (placeOrderBtn) {
  placeOrderBtn.addEventListener("click", async function () {
    const message = document.getElementById("order-message");
    const selection = currentSelection();

    if (selection.length === 0) {
      message.className = "message-error";
      message.textContent = "Vui lòng chọn ít nhất một món";
      const firstQty = document.querySelector(".quantity-input");
      if (firstQty) firstQty.focus();
      return;
    }

    setBusy(placeOrderBtn, true, "Đang gửi đơn");
    try {
      await apiJson("/orders", "POST", {
        items: selection.map((i) => ({ menu_item_id: i.menu_item_id, quantity: i.quantity })),
        order_date: selectedDate,
      });

      const forDay = selectedDate === todayIso ? "hôm nay" : dayLabel(selectedDate).toLowerCase();
      message.className = "message-success";
      message.textContent = `Đã gửi đơn cho ${forDay}`;
      showToast(selectedDate === todayIso ? "Đặt món thành công" : "Đã đặt trước thành công", {
        body: `${forDay} · ${selection.length} món · ${money(
          selection.reduce((s, i) => s + i.price * i.quantity, 0)
        )}`,
        type: "success",
      });
      await Promise.all([loadMyOrder(), loadAvailableDates()]);
    } catch (err) {
      message.className = "message-error";
      message.textContent = err.message;
      showToast("Đặt món thất bại", { body: err.message, type: "error" });
    } finally {
      setBusy(placeOrderBtn, false);
    }
  });
}

// ----- Hộp thoại thanh toán -----

const paymentMethodBtn = document.getElementById("payment-method-btn");
const paymentModalOverlay = document.getElementById("payment-modal-overlay");

async function fetchAdminPaymentInfo() {
  if (adminPaymentInfo) return adminPaymentInfo;
  try {
    adminPaymentInfo = await apiRequest("/payment-info");
  } catch (err) {
    adminPaymentInfo = { name: null, phone: null, qr_image_url: null };
  }
  return adminPaymentInfo;
}

function renderPaymentInfoPanel() {
  const panel = document.getElementById("payment-info-panel");
  if (!panel || !adminPaymentInfo) return;
  panel.innerHTML = "";

  const collector = adminPaymentInfo.name || "người đặt";

  // Thông tin liên lạc của người đứng ra đặt
  const contact = document.createElement("div");
  contact.className = "card";
  contact.style.margin = "0";

  const lead = document.createElement("p");
  lead.className = "subtitle";
  lead.style.margin = "0 0 4px";
  lead.textContent = "Chuyển khoản cho:";

  const name = document.createElement("p");
  name.style.cssText = "margin:0; font-weight:600;";
  name.textContent = collector;
  contact.append(lead, name);

  if (adminPaymentInfo.phone) {
    const phone = document.createElement("p");
    phone.className = "mono";
    phone.style.margin = "4px 0 0";
    phone.textContent = adminPaymentInfo.phone;
    contact.appendChild(phone);
  } else {
    const missing = document.createElement("p");
    missing.className = "subtitle";
    missing.style.margin = "4px 0 0";
    missing.textContent = "Chưa có số liên hệ.";
    contact.appendChild(missing);
  }

  panel.appendChild(contact);

  // Mã QR
  const qrBox = document.createElement("div");
  qrBox.className = "card";
  qrBox.style.cssText = "margin:0; text-align:center;";

  if (adminPaymentInfo.qr_image_url) {
    const qrLead = document.createElement("p");
    qrLead.className = "subtitle";
    qrLead.style.margin = "0 0 8px";
    qrLead.textContent = "Quét mã để chuyển khoản:";
    const img = document.createElement("img");
    img.className = "qr-frame";
    img.src = assetUrl(adminPaymentInfo.qr_image_url);
    img.alt = `Mã QR chuyển khoản của ${collector}`;
    qrBox.append(qrLead, img);
  } else {
    qrBox.textContent = "Người đặt chưa cập nhật mã QR chuyển khoản.";
  }

  panel.appendChild(qrBox);
}

async function renderOrderSummaryPanel() {
  const panel = document.getElementById("order-summary-panel");
  if (!panel) return;
  panel.innerHTML = "";

  const items = myOrder
    ? myOrder.items.map((i) => ({ name: i.name, price: i.price, quantity: i.quantity }))
    : currentSelection();

  if (items.length === 0) {
    const p = document.createElement("p");
    p.className = "subtitle";
    p.style.margin = "0";
    p.textContent = "Chưa có món nào được chọn.";
    panel.appendChild(p);
    return;
  }

  const card = document.createElement("div");
  card.className = "card";
  card.style.margin = "0";

  const list = document.createElement("ul");
  list.style.cssText = "margin:0; padding-left:18px;";
  items.forEach((i) => {
    const li = document.createElement("li");
    li.textContent = `${i.name} × ${i.quantity} — ${money(i.price * i.quantity)}`;
    list.appendChild(li);
  });

  const total = document.createElement("p");
  total.style.cssText = "margin:8px 0 0; font-weight:600;";
  total.textContent = `Thành tiền: ${money(
    items.reduce((sum, i) => sum + i.price * i.quantity, 0)
  )}`;

  card.append(list, total);
  panel.appendChild(card);
}

function setPaymentStep(step) {
  const choose = document.getElementById("payment-step-choose");
  const success = document.getElementById("payment-step-success");
  if (!choose || !success) return;
  choose.hidden = step !== "choose";
  success.hidden = step !== "success";
}

let lastFocusedBeforeModal = null;

function openPaymentModal() {
  if (!paymentModalOverlay) return;
  lastFocusedBeforeModal = document.activeElement;
  paymentModalOverlay.hidden = false;
  paymentModalOverlay.style.display = "flex";
  setPaymentStep("choose");
  setText(document.getElementById("payment-modal-message"), "");

  const confirmBtn = document.getElementById("payment-confirm-btn");
  if (confirmBtn) confirmBtn.focus();
}

function closePaymentModal() {
  if (!paymentModalOverlay) return;
  paymentModalOverlay.style.display = "none";
  paymentModalOverlay.hidden = true;
  if (lastFocusedBeforeModal) lastFocusedBeforeModal.focus();
}

if (paymentMethodBtn && paymentModalOverlay) {
  paymentMethodBtn.addEventListener("click", async function () {
    openPaymentModal();
    await renderOrderSummaryPanel();
    await fetchAdminPaymentInfo();
    renderPaymentInfoPanel();
  });

  // Báo đã chuyển khoản -> đóng lại và chờ người đặt xác nhận đã nhận tiền
  const confirmBtn = document.getElementById("payment-confirm-btn");
  confirmBtn.addEventListener("click", async function () {
    const message = document.getElementById("payment-modal-message");

    if (!myOrder) {
      message.className = "message-error";
      message.textContent = "Bạn chưa có đơn nào hôm nay để thanh toán.";
      return;
    }
    if (myOrder.status === "pending") {
      message.className = "message-error";
      message.textContent = "Đơn chưa được chốt, chờ người đặt chốt đơn đã nhé.";
      return;
    }

    setBusy(confirmBtn, true, "Đang gửi báo chuyển khoản");
    try {
      const result = await apiJson(`/orders/${myOrder.id}/pay`, "POST");
      const order = result.order;
      const collector = (adminPaymentInfo && adminPaymentInfo.name) || "người đặt";

      setText(document.getElementById("pay-success-amount"), money(order.total_cost));
      setText(
        document.getElementById("pay-success-meta"),
        `Đơn #${order.id} · đang chờ ${collector} xác nhận đã nhận tiền`
      );
      setPaymentStep("success");
      document.getElementById("payment-success-close").focus();

      showToast("Đã báo chuyển khoản", {
        body: `Chờ ${collector} xác nhận đã nhận ${money(order.total_cost)}`,
        type: "info",
      });
      await loadMyOrder();
    } catch (err) {
      message.className = "message-error";
      message.textContent = err.message;
    } finally {
      setBusy(confirmBtn, false);
    }
  });

  document.getElementById("payment-success-close").addEventListener("click", closePaymentModal);
  document.getElementById("payment-modal-cancel").addEventListener("click", closePaymentModal);

  paymentModalOverlay.addEventListener("click", function (e) {
    if (e.target === paymentModalOverlay) closePaymentModal();
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && paymentModalOverlay.style.display === "flex") {
      closePaymentModal();
    }
  });
}

// Khởi động trang thực đơn
if (menuList) {
  renderStepper();
  (async () => {
    await loadAvailableDates();
    await Promise.all([loadMenu(), loadMyOrder()]);
  })();

  onRealtime("orders_locked", (data) => {
    // Chỉ báo khi đúng ngày đang xem bị chốt
    if (!data.date || data.date === selectedDate) {
      showToast("Đơn đã được chốt", {
        body: "Người đặt đang đặt trên Grab.",
        type: "info",
      });
    }
    loadMyOrder();
    loadMenu();
    loadAvailableDates();
  });

  onRealtime("orders_ordered", () => {
    showToast("Quán đã nhận đơn", { body: "Đến lúc chuyển khoản rồi.", type: "success" });
    loadMyOrder();
  });

  onRealtime("payment_confirmed", () => {
    // Chỉ báo cho đúng người vừa được xác nhận
    if (myOrder && myOrder.awaiting_confirmation) {
      showToast("Người đặt đã xác nhận nhận tiền", { type: "success" });
    }
    loadMyOrder();
  });

  // Quản trị viên vừa lên thực đơn ngày mới thì dải chọn ngày phải hiện thêm ngày đó
  onRealtime("menu_updated", () => {
    loadMenu();
    loadAvailableDates();
  });

  connectRealtime();
}

// ===================================================================
//  TRANG LỊCH SỬ
// ===================================================================

const historyList = document.getElementById("history-list");

// Nhãn + kiểu hiển thị cho tình trạng thanh toán của một đơn trong lịch sử
const PAYMENT_STATE_BADGE = {
  confirmed: "completed",
  awaiting: "pending",
  unpaid: "unpaid",
  not_due: "closed",
};

function formatMoment(value) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("vi-VN", {
    hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit", year: "numeric",
  });
}

/** Một đơn trong lịch sử: bấm vào để mở bảng chi tiết món / số lượng / thành tiền. */
function buildHistoryCard(order, index) {
  const card = document.createElement("article");
  card.className = "card history-card";

  const detailId = `history-detail-${order.id}`;

  // ----- Dòng tóm tắt, bấm được để mở/đóng -----
  const summary = document.createElement("button");
  summary.type = "button";
  summary.className = "history-summary";
  summary.setAttribute("aria-expanded", "false");
  summary.setAttribute("aria-controls", detailId);

  const caret = document.createElement("span");
  caret.className = "h-caret";
  caret.setAttribute("aria-hidden", "true");
  caret.textContent = "›";

  const date = document.createElement("span");
  date.className = "h-date";
  date.textContent = order.order_date;

  const statusBadge = document.createElement("span");
  statusBadge.className = `badge ${statusBadgeClass(order.status)}`;
  statusBadge.textContent = order.status_label || order.status;

  // Đã thanh toán chưa, và người đặt đã xác nhận nhận tiền chưa
  const payBadge = document.createElement("span");
  payBadge.className = `badge ${PAYMENT_STATE_BADGE[order.payment_state] || "pending"}`;
  payBadge.textContent = order.payment_label;

  const spacer = document.createElement("span");
  spacer.className = "h-spacer";

  const total = document.createElement("span");
  total.className = "h-total";
  total.textContent = money(order.total_cost);

  summary.append(caret, date, statusBadge, payBadge, spacer, total);

  const srHint = document.createElement("span");
  srHint.className = "sr-only";
  srHint.textContent = `Xem chi tiết hóa đơn ngày ${order.order_date}`;
  summary.appendChild(srHint);

  // ----- Bảng chi tiết -----
  const detail = document.createElement("div");
  detail.className = "history-detail";
  detail.id = detailId;
  detail.hidden = true;

  const wrap = document.createElement("div");
  wrap.className = "table-wrap";
  wrap.style.border = "none";
  wrap.style.marginBottom = "0";

  const table = document.createElement("table");
  table.innerHTML =
    "<thead><tr><th scope='col'>Món ăn</th><th scope='col' class='num'>Đơn giá</th>" +
    "<th scope='col' class='num'>Số lượng</th><th scope='col' class='num'>Thành tiền</th></tr></thead>";

  const tbody = document.createElement("tbody");
  order.items.forEach((item) => {
    const tr = document.createElement("tr");

    const name = document.createElement("td");
    name.textContent = item.name;
    if (item.restaurant_name) {
      const shop = document.createElement("div");
      shop.className = "subtitle";
      shop.style.margin = "2px 0 0";
      shop.style.fontSize = "12.5px";
      shop.textContent = item.restaurant_name;
      name.appendChild(shop);
    }

    const price = document.createElement("td");
    price.className = "num mono";
    price.textContent = money(item.price);

    const qty = document.createElement("td");
    qty.className = "num mono";
    qty.textContent = `× ${item.quantity}`;

    const line = document.createElement("td");
    line.className = "num mono";
    line.textContent = money(item.line_cost);

    tr.append(name, price, qty, line);
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);

  const tfoot = document.createElement("tfoot");
  const footRow = document.createElement("tr");
  const footLabel = document.createElement("td");
  footLabel.colSpan = 3;
  footLabel.textContent = "Tổng cộng";
  const footValue = document.createElement("td");
  footValue.className = "num mono";
  footValue.textContent = money(order.total_cost);
  footRow.append(footLabel, footValue);
  tfoot.appendChild(footRow);
  table.appendChild(tfoot);

  wrap.appendChild(table);
  detail.appendChild(wrap);

  // Dòng trạng thái thanh toán chi tiết
  const payState = document.createElement("div");
  payState.className = "pay-state";

  const parts = [];
  if (order.paid_at) {
    parts.push(`Bạn báo đã chuyển lúc ${formatMoment(order.paid_at)}`);
  }
  if (order.payment_confirmed_at) {
    parts.push(
      `${order.collector_name || "Người đặt"} xác nhận nhận tiền lúc ${formatMoment(order.payment_confirmed_at)}`
    );
  } else if (order.paid_at) {
    parts.push(`Đang chờ ${order.collector_name || "người đặt"} xác nhận`);
  }
  payState.textContent = parts.length ? parts.join(" · ") : order.payment_label;
  detail.appendChild(payState);

  summary.addEventListener("click", () => {
    const open = summary.getAttribute("aria-expanded") === "true";
    summary.setAttribute("aria-expanded", String(!open));
    detail.hidden = open;
  });

  // Mở sẵn đơn gần nhất để không phải bấm thêm một lần
  if (index === 0) {
    summary.setAttribute("aria-expanded", "true");
    detail.hidden = false;
  }

  card.append(summary, detail);
  return card;
}

if (historyList) {
  (async function loadHistory() {
    try {
      const data = await apiRequest("/orders/history");
      historyList.innerHTML = "";

      if (!data.history.length) {
        historyList.innerHTML =
          '<div class="empty-state"><div class="icon" aria-hidden="true">🕘</div>' +
          "Chưa có lịch sử đặt món.</div>";
        return;
      }

      data.history.forEach((order, index) => historyList.appendChild(buildHistoryCard(order, index)));
    } catch (err) {
      historyList.innerHTML =
        '<div class="empty-state"><div class="icon" aria-hidden="true">⚠️</div>' +
        "Không tải được lịch sử.</div>";
    }
  })();
}

// ===================================================================
//  TRANG QUẢN TRỊ — ĐẶT HÀNG
// ===================================================================

const restaurantForm = document.getElementById("restaurant-form");
const menuForm = document.getElementById("menu-form");
const dashboardBox = document.getElementById("dashboard-box");

let restaurants = [];
let pendingRestaurantPreview = null;
let uploadedItemImageUrl = null;
let uploadedQrUrl = null;

// Ngày đang xem trên bảng điều khiển — cho phép mở đơn đặt trước của hôm sau
let adminDate = null;

// ----- Nhà hàng từ GrabFood -----

async function loadRestaurants() {
  const select = document.getElementById("item-restaurant");
  const listBox = document.getElementById("restaurant-list");

  try {
    const data = await apiRequest("/restaurants");
    restaurants = data.restaurants || [];
  } catch (err) {
    restaurants = [];
  }

  if (select) {
    const previous = select.value;
    select.innerHTML = '<option value="">— Chọn nhà hàng —</option>';
    restaurants.forEach((r) => {
      const option = document.createElement("option");
      option.value = r.id;
      option.textContent = r.rating ? `${r.name} (${Number(r.rating).toFixed(1)}★)` : r.name;
      select.appendChild(option);
    });
    if (previous) select.value = previous;
    updateMenuFormAvailability();
  }

  if (listBox) {
    listBox.innerHTML = "";
    if (!restaurants.length) {
      listBox.innerHTML =
        '<div class="empty-state"><div class="icon" aria-hidden="true">🏪</div>' +
        "Chưa có nhà hàng nào. Dán đường dẫn GrabFood ở trên để thêm.</div>";
      return;
    }

    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    const table = document.createElement("table");
    table.innerHTML =
      "<caption>Nhà hàng đã lưu</caption>" +
      "<thead><tr><th scope='col'>Tên quán</th><th scope='col'>Đánh giá</th>" +
      "<th scope='col'>Địa chỉ</th><th scope='col'>Grab</th><th scope='col'>Thao tác</th></tr></thead>";

    const tbody = document.createElement("tbody");
    restaurants.forEach((r) => {
      const tr = document.createElement("tr");

      const name = document.createElement("td");
      name.textContent = r.name;

      const rating = document.createElement("td");
      rating.className = "num";
      rating.textContent = r.rating ? `${Number(r.rating).toFixed(1)} / 5` : "—";

      const address = document.createElement("td");
      address.textContent = r.address || "—";

      const link = document.createElement("td");
      if (r.grab_url) {
        const a = document.createElement("a");
        a.href = r.grab_url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.className = "link-action";
        a.textContent = "Mở Grab";
        a.setAttribute("aria-label", `Mở trang GrabFood của ${r.name} trong tab mới`);
        link.appendChild(a);
      } else {
        link.textContent = "—";
      }

      const actions = document.createElement("td");
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "danger";
      remove.textContent = "Xóa";
      remove.setAttribute("aria-label", `Xóa nhà hàng ${r.name}`);
      remove.addEventListener("click", async () => {
        if (!window.confirm(`Xóa nhà hàng "${r.name}"?`)) return;
        setBusy(remove, true, "Đang xóa");
        try {
          await apiRequest(`/admin/restaurants/${r.id}`, { method: "DELETE" });
          showToast("Đã xóa nhà hàng", { type: "info" });
          await loadRestaurants();
        } catch (err) {
          setBusy(remove, false);
          showToast("Không xóa được", { body: err.message, type: "error" });
        }
      });
      actions.appendChild(remove);

      tr.append(name, rating, address, link, actions);
      tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    wrap.appendChild(table);
    listBox.appendChild(wrap);
  }
}

function renderRestaurantPreview(info, hint) {
  const box = document.getElementById("restaurant-preview");
  if (!box) return;
  box.innerHTML = "";
  pendingRestaurantPreview = info;

  const card = document.createElement("div");
  card.className = "card";

  const heading = document.createElement("h3");
  heading.textContent = "Kiểm tra thông tin trước khi lưu";
  card.appendChild(heading);

  if (hint) {
    const notice = document.createElement("div");
    notice.className = "notice info";
    notice.style.marginBottom = "12px";
    notice.appendChild(document.createTextNode(hint));
    card.appendChild(notice);
  }

  const grid = document.createElement("div");
  grid.style.cssText = "display:flex; flex-wrap:wrap; gap:12px;";

  const makeField = (id, labelText, value, type = "text") => {
    const field = document.createElement("div");
    field.className = "field";
    const label = document.createElement("label");
    label.setAttribute("for", id);
    label.textContent = labelText;
    const input = document.createElement("input");
    input.type = type;
    input.id = id;
    input.value = value || "";
    if (type === "number") {
      input.min = "0";
      input.max = "5";
      input.step = "0.1";
    }
    field.append(label, input);
    grid.appendChild(field);
    return input;
  };

  const nameInput = makeField("preview-name", "Tên nhà hàng", info.name);
  const addressInput = makeField("preview-address", "Địa chỉ", info.address);
  const ratingInput = makeField("preview-rating", "Đánh giá (0–5)", info.rating, "number");

  card.appendChild(grid);

  const save = document.createElement("button");
  save.type = "button";
  save.textContent = "Lưu nhà hàng";
  save.style.marginTop = "12px";
  save.addEventListener("click", async () => {
    if (!nameInput.value.trim()) {
      nameInput.setAttribute("aria-invalid", "true");
      nameInput.focus();
      showToast("Thiếu tên nhà hàng", { type: "warning" });
      return;
    }
    setBusy(save, true, "Đang lưu nhà hàng");
    try {
      await apiJson("/admin/restaurants", "POST", {
        name: nameInput.value.trim(),
        address: addressInput.value.trim(),
        rating: ratingInput.value,
        grab_url: info.grab_url,
        external_id: info.external_id,
      });
      showToast("Đã lưu nhà hàng", { body: nameInput.value.trim(), type: "success" });
      box.innerHTML = "";
      pendingRestaurantPreview = null;
      document.getElementById("grab-url").value = "";
      await loadRestaurants();
    } catch (err) {
      setBusy(save, false);
      showToast("Lưu thất bại", { body: err.message, type: "error" });
    }
  });

  card.appendChild(save);
  box.appendChild(card);
  nameInput.focus();
}

if (restaurantForm) {
  const fetchBtn = document.getElementById("grab-fetch-btn");
  const urlInput = document.getElementById("grab-url");

  const runPreview = async () => {
    urlInput.removeAttribute("aria-invalid");
    if (!urlInput.value.trim()) {
      urlInput.setAttribute("aria-invalid", "true");
      urlInput.focus();
      showToast("Chưa có đường dẫn", {
        body: "Dán đường dẫn nhà hàng trên GrabFood vào ô này.",
        type: "warning",
      });
      return;
    }

    setBusy(fetchBtn, true, "Đang lấy thông tin nhà hàng");
    try {
      const data = await apiJson("/admin/restaurants/preview", "POST", {
        grab_url: urlInput.value.trim(),
      });
      renderRestaurantPreview(data.restaurant, data.hint);
    } catch (err) {
      urlInput.setAttribute("aria-invalid", "true");
      showToast("Không đọc được đường dẫn", { body: err.message, type: "error" });
    } finally {
      setBusy(fetchBtn, false);
    }
  };

  fetchBtn.addEventListener("click", runPreview);
  restaurantForm.addEventListener("submit", (e) => {
    e.preventDefault();
    runPreview();
  });
}

// ----- Thực đơn: chọn nhà hàng trước rồi mới thêm món -----

function updateMenuFormAvailability() {
  const select = document.getElementById("item-restaurant");
  const submit = document.getElementById("menu-submit-btn");
  if (!select || !submit) return;

  const hasRestaurants = restaurants.length > 0;
  const chosen = Boolean(select.value);

  select.disabled = !hasRestaurants;
  submit.disabled = !chosen;
  submit.title = chosen ? "" : "Chọn nhà hàng trước khi thêm món";

  ["item-name", "item-price", "item-date", "item-description", "item-image"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.disabled = !chosen;
  });
}

if (menuForm) {
  const dateInput = document.getElementById("item-date");
  if (dateInput && !dateInput.value) {
    dateInput.value = new Date().toISOString().slice(0, 10);
  }

  document.getElementById("item-restaurant").addEventListener("change", updateMenuFormAvailability);

  // Chọn ảnh -> tải lên ngay và hiện xem trước
  const imageInput = document.getElementById("item-image");
  const imagePreview = document.getElementById("item-image-preview");
  const imageEmpty = document.getElementById("item-image-empty");

  imageInput.addEventListener("change", async function () {
    const file = imageInput.files && imageInput.files[0];
    if (!file) {
      uploadedItemImageUrl = null;
      imagePreview.hidden = true;
      imageEmpty.hidden = false;
      return;
    }

    // Hiện trước ngay từ máy người dùng, không phải chờ mạng
    const localUrl = URL.createObjectURL(file);
    imagePreview.src = localUrl;
    imagePreview.hidden = false;
    imageEmpty.hidden = true;

    try {
      const result = await uploadImage(file);
      uploadedItemImageUrl = result.url;
      imagePreview.src = assetUrl(result.url);
      URL.revokeObjectURL(localUrl);
    } catch (err) {
      uploadedItemImageUrl = null;
      imagePreview.hidden = true;
      imageEmpty.hidden = false;
      imageInput.value = "";
      showToast("Tải ảnh thất bại", { body: err.message, type: "error" });
    }
  });

  menuForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    const message = document.getElementById("menu-form-message");
    const submitBtn = document.getElementById("menu-submit-btn");

    const restaurantSelect = document.getElementById("item-restaurant");
    const nameInput = document.getElementById("item-name");
    const priceInput = document.getElementById("item-price");
    const dateField = document.getElementById("item-date");

    // Kiểm tra tại chỗ, báo lỗi ngay dưới ô sai và đưa focus về đó
    const checks = [
      [restaurantSelect, "item-restaurant-error", !restaurantSelect.value, "Vui lòng chọn nhà hàng"],
      [nameInput, "item-name-error", !nameInput.value.trim(), "Vui lòng nhập tên món"],
      [priceInput, "item-price-error", !priceInput.value || Number(priceInput.value) <= 0,
        "Giá phải lớn hơn 0"],
    ];

    let firstInvalid = null;
    checks.forEach(([el, errorId, invalid, text]) => {
      setText(document.getElementById(errorId), invalid ? text : "");
      if (invalid) {
        el.setAttribute("aria-invalid", "true");
        if (!firstInvalid) firstInvalid = el;
      } else {
        el.removeAttribute("aria-invalid");
      }
    });

    if (firstInvalid) {
      firstInvalid.focus();
      return;
    }

    setBusy(submitBtn, true, "Đang thêm món");
    try {
      await apiJson("/admin/menu", "POST", {
        name: nameInput.value.trim(),
        description: document.getElementById("item-description").value.trim(),
        price: parseFloat(priceInput.value),
        available_date: dateField.value,
        restaurant_id: parseInt(restaurantSelect.value, 10),
        image_url: uploadedItemImageUrl,
      });

      message.className = "message-success";
      message.textContent = "Đã thêm món vào thực đơn";
      showToast("Đã thêm món", { body: nameInput.value.trim(), type: "success" });

      // Giữ lại nhà hàng và ngày để thêm món tiếp cho nhanh
      nameInput.value = "";
      priceInput.value = "";
      document.getElementById("item-description").value = "";
      document.getElementById("item-image").value = "";
      uploadedItemImageUrl = null;
      document.getElementById("item-image-preview").hidden = true;
      document.getElementById("item-image-empty").hidden = false;
      nameInput.focus();

      loadDashboard();
    } catch (err) {
      message.className = "message-error";
      message.textContent = err.message;
      showToast("Thêm món thất bại", { body: err.message, type: "error" });
    } finally {
      setBusy(submitBtn, false);
    }
  });
}

// ----- Bảng điều khiển gộp -----

function renderDashboard(data) {
  if (!dashboardBox) return;
  dashboardBox.setAttribute("aria-busy", "false");
  dashboardBox.innerHTML = "";

  setText(document.getElementById("dashboard-total"), money(data.totals.grand_total));

  const stats = document.getElementById("dashboard-stats");
  stats.innerHTML = "";
  [
    { label: "Nhân viên đã đặt", value: data.totals.employee_count },
    { label: "Tổng số phần", value: data.totals.item_count },
    { label: "Đã nhận tiền", value: `${data.totals.paid_count}/${data.totals.employee_count}` },
    { label: "Chờ xác nhận", value: data.totals.awaiting_count, accent: data.totals.awaiting_count > 0 },
  ].forEach((item) => {
    const box = document.createElement("div");
    box.className = `stat${item.accent ? " is-accent" : ""}`;
    const label = document.createElement("div");
    label.className = "stat-label";
    label.textContent = item.label;
    const value = document.createElement("div");
    value.className = "stat-value";
    value.textContent = item.value;
    box.append(label, value);
    stats.appendChild(box);
  });

  setText(
    document.getElementById("dashboard-heading"),
    data.is_today ? "3. Bảng điều khiển đơn hôm nay"
                  : `3. Bảng điều khiển đơn ${dayLabelAdmin(data.date, data.today).toLowerCase()} (${data.date})`
  );

  const lockBtn = document.getElementById("lock-orders-btn");
  if (lockBtn) {
    lockBtn.disabled = data.locked || data.totals.employee_count === 0;
    lockBtn.textContent = data.locked ? "Đơn đã chốt" : "Chốt đơn & đặt trên Grab";
  }

  const exportLink = document.getElementById("export-link");
  if (exportLink) exportLink.href = `${API_BASE}/admin/orders/export?date=${data.date}`;

  if (!data.employees.length) {
    dashboardBox.innerHTML =
      '<div class="empty-state"><div class="icon" aria-hidden="true">📋</div>' +
      "Chưa có nhân viên nào đặt món hôm nay.</div>";
    return;
  }

  // Bảng 1: tổng hợp theo món — dùng để gõ vào Grab
  const summaryWrap = document.createElement("div");
  summaryWrap.className = "table-wrap";
  const summaryTable = document.createElement("table");
  summaryTable.innerHTML =
    "<caption>Tổng hợp theo món — dùng bảng này để đặt trên Grab</caption>" +
    "<thead><tr><th scope='col'>Nhà hàng</th><th scope='col'>Món ăn</th>" +
    "<th scope='col' class='num'>Đơn giá</th><th scope='col' class='num'>Số phần</th>" +
    "<th scope='col' class='num'>Thành tiền</th></tr></thead>";

  const summaryBody = document.createElement("tbody");
  data.summary.forEach((row) => {
    const tr = document.createElement("tr");
    const cells = [
      row.restaurant_name || "—",
      row.item_name,
      money(row.price),
      String(row.total_quantity),
      money(row.price * row.total_quantity),
    ];
    cells.forEach((value, index) => {
      const td = document.createElement("td");
      if (index >= 2) td.className = "num";
      td.textContent = value;
      tr.appendChild(td);
    });
    summaryBody.appendChild(tr);
  });
  summaryTable.appendChild(summaryBody);
  summaryWrap.appendChild(summaryTable);
  dashboardBox.appendChild(summaryWrap);

  // Bảng 2: chi tiết theo nhân viên — dùng để thu tiền
  const empWrap = document.createElement("div");
  empWrap.className = "table-wrap";
  const empTable = document.createElement("table");
  empTable.innerHTML =
    "<caption>Chi tiết theo nhân viên — dùng bảng này để thu tiền</caption>" +
    "<thead><tr><th scope='col'>Nhân viên</th><th scope='col'>Món đã đặt</th>" +
    "<th scope='col' class='num'>Thành tiền</th><th scope='col'>Trạng thái</th>" +
    "<th scope='col'>Thanh toán</th></tr></thead>";

  const empBody = document.createElement("tbody");
  data.employees.forEach((emp) => {
    const tr = document.createElement("tr");

    const name = document.createElement("td");
    name.textContent = emp.employee_name;

    const items = document.createElement("td");
    items.textContent = emp.items.map((i) => `${i.item_name} × ${i.quantity}`).join(", ");

    const cost = document.createElement("td");
    cost.className = "num mono";
    cost.textContent = money(emp.total_cost);

    const status = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = `badge ${statusBadgeClass(emp.status)}`;
    badge.textContent = emp.status_label;
    status.appendChild(badge);

    const payment = document.createElement("td");
    if (emp.confirmed) {
      const paidBadge = document.createElement("span");
      paidBadge.className = "badge completed";
      paidBadge.textContent = "Đã nhận tiền";
      payment.appendChild(paidBadge);
    } else if (emp.status === "pending") {
      payment.textContent = "Chưa chốt";
      payment.style.color = "var(--text-secondary)";
    } else {
      // Đã chốt đơn thì quản trị viên xác nhận được, kể cả khi nhân viên chưa bấm báo
      const wrap = document.createElement("div");
      wrap.style.cssText = "display:flex; flex-direction:column; gap:6px; align-items:flex-start;";

      const state = document.createElement("span");
      state.className = `badge ${emp.awaiting_confirmation ? "pending" : "unpaid"}`;
      state.textContent = emp.awaiting_confirmation ? "Báo đã chuyển" : "Chưa chuyển";
      wrap.appendChild(state);

      const confirm = document.createElement("button");
      confirm.type = "button";
      confirm.className = emp.awaiting_confirmation ? "" : "ghost";
      confirm.textContent = "Đã nhận tiền";
      confirm.setAttribute(
        "aria-label",
        `Xác nhận đã nhận tiền của ${emp.employee_name}, ${money(emp.total_cost)}`
      );
      confirm.addEventListener("click", async () => {
        setBusy(confirm, true, "Đang xác nhận");
        try {
          await apiJson(`/admin/orders/${emp.order_id}/confirm-payment`, "POST");
          showToast("Đã xác nhận nhận tiền", {
            body: `${emp.employee_name} · ${money(emp.total_cost)}`,
            type: "success",
          });
          await loadDashboard();
        } catch (err) {
          setBusy(confirm, false);
          showToast("Xác nhận thất bại", { body: err.message, type: "error" });
        }
      });
      wrap.appendChild(confirm);
      payment.appendChild(wrap);
    }

    tr.append(name, items, cost, status, payment);
    empBody.appendChild(tr);
  });
  empTable.appendChild(empBody);

  const foot = document.createElement("tfoot");
  const footRow = document.createElement("tr");
  const footLabel = document.createElement("td");
  footLabel.colSpan = 2;
  footLabel.textContent = "Tổng cộng";
  const footValue = document.createElement("td");
  footValue.className = "num mono";
  footValue.textContent = money(data.totals.grand_total);
  const footRest = document.createElement("td");
  footRest.colSpan = 2;
  footRow.append(footLabel, footValue, footRest);
  foot.appendChild(footRow);
  empTable.appendChild(foot);

  empWrap.appendChild(empTable);
  dashboardBox.appendChild(empWrap);

  const note = document.createElement("p");
  note.className = "note";
  note.textContent =
    'Cột "Thanh toán" chỉ hiện sau khi đơn đã chốt — trước đó nhân viên vẫn có thể đổi ý.';
  dashboardBox.appendChild(note);
}

function renderAdminDatePicker(data) {
  const picker = document.getElementById("admin-date-picker");
  if (!picker) return;

  const dates = data.available_dates || [];
  if (dates.length < 2) {
    picker.hidden = true;
    picker.innerHTML = "";
    return;
  }

  picker.hidden = false;
  picker.innerHTML = "";

  dates.forEach((iso) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "date-chip";
    chip.setAttribute("aria-pressed", String(iso === data.date));

    const day = document.createElement("span");
    day.className = "chip-day";
    const isToday = iso === data.today;
    day.textContent = `${isToday ? "Hôm nay" : dayLabelAdmin(iso, data.today)} · ${shortDate(iso)}`;

    const meta = document.createElement("span");
    meta.className = "chip-meta";
    meta.textContent = iso;

    chip.append(day, meta);
    chip.addEventListener("click", () => {
      if (iso === adminDate) return;
      adminDate = iso;
      loadDashboard();
    });
    picker.appendChild(chip);
  });
}

function dayLabelAdmin(iso, today) {
  const parsed = new Date(`${iso}T00:00:00`);
  const base = new Date(`${today}T00:00:00`);
  const diff = Math.round((parsed - base) / 86400000);
  if (diff === 0) return "Hôm nay";
  if (diff === 1) return "Ngày mai";
  return WEEKDAY_LABELS[parsed.getDay()] || iso;
}

async function loadDashboard() {
  if (!dashboardBox) return;
  try {
    const query = adminDate ? `?date=${encodeURIComponent(adminDate)}` : "";
    const data = await apiRequest(`/admin/dashboard${query}`);
    adminDate = data.date;
    renderAdminDatePicker(data);
    renderDashboard(data);
  } catch (err) {
    dashboardBox.setAttribute("aria-busy", "false");
    dashboardBox.innerHTML =
      '<div class="empty-state"><div class="icon" aria-hidden="true">⚠️</div>' +
      "Không tải được bảng điều khiển. <div class='empty-action'>" +
      "<button type='button' id='dashboard-retry'>Thử lại</button></div></div>";
    const retry = document.getElementById("dashboard-retry");
    if (retry) retry.addEventListener("click", loadDashboard);
  }
}

// ----- Hành động chính: chốt đơn và mở Grab -----

const lockOrdersBtn = document.getElementById("lock-orders-btn");
if (lockOrdersBtn) {
  lockOrdersBtn.addEventListener("click", async function () {
    const message = document.getElementById("lock-orders-message");

    if (!window.confirm("Chốt đơn hôm nay? Sau bước này nhân viên không sửa đơn được nữa.")) {
      return;
    }

    setBusy(lockOrdersBtn, true, "Đang chốt đơn");
    try {
      const data = await apiJson("/admin/orders/lock", "POST", { date: adminDate });

      message.className = "message-success";
      message.textContent = `Đã chốt ${data.locked_count} đơn.`;

      // Mở thẳng trang Grab của các quán liên quan
      const links = data.grab_links || [];
      if (links.length) {
        links.forEach((r, index) => {
          // Mở lần lượt, tránh trình duyệt chặn hàng loạt popup
          window.setTimeout(() => {
            window.open(r.grab_url, "_blank", "noopener,noreferrer");
          }, index * 400);
        });

        showToast("Đang mở Grab", {
          body: `${links.length} quán cần đặt: ${links.map((r) => r.name).join(", ")}`,
          type: "info",
        });

        // Đơn chuyển sang trạng thái chờ thanh toán, nhân viên thấy nút sáng lên
        await apiJson("/admin/orders/grab-placed", "POST", { date: adminDate });
      } else {
        message.className = "message-error";
        message.textContent =
          "Đã chốt đơn, nhưng chưa quán nào có đường dẫn Grab — hãy bổ sung ở mục 1.";
        showToast("Chưa có đường dẫn Grab", {
          body: "Bổ sung đường dẫn GrabFood cho nhà hàng để mở tự động.",
          type: "warning",
        });
      }

      await loadDashboard();
    } catch (err) {
      message.className = "message-error";
      message.textContent = err.message;
      showToast("Chốt đơn thất bại", { body: err.message, type: "error" });
    } finally {
      setBusy(lockOrdersBtn, false);
    }
  });
}

const dashboardRefreshBtn = document.getElementById("dashboard-refresh-btn");
if (dashboardRefreshBtn) {
  dashboardRefreshBtn.addEventListener("click", async () => {
    setBusy(dashboardRefreshBtn, true, "Đang làm mới");
    await loadDashboard();
    setBusy(dashboardRefreshBtn, false);
  });
}

// ----- Thông tin nhận tiền của quản trị viên -----

const paymentInfoForm = document.getElementById("payment-info-form");

if (paymentInfoForm) {
  const qrInput = document.getElementById("admin-qr-file");
  const qrPreview = document.getElementById("qr-preview-img");
  const qrEmpty = document.getElementById("qr-preview-empty");

  const showQr = (url) => {
    if (url) {
      qrPreview.src = assetUrl(url);
      qrPreview.hidden = false;
      qrEmpty.hidden = true;
    } else {
      qrPreview.hidden = true;
      qrEmpty.hidden = false;
    }
  };

  (async function loadOwnPaymentInfo() {
    try {
      const data = await apiRequest("/payment-info");
      document.getElementById("admin-phone").value = data.phone || "";
      uploadedQrUrl = data.qr_image_url || null;
      showQr(uploadedQrUrl);
    } catch (err) {
      showQr(null);
    }
  })();

  qrInput.addEventListener("change", async function () {
    const file = qrInput.files && qrInput.files[0];
    if (!file) return;

    const localUrl = URL.createObjectURL(file);
    qrPreview.src = localUrl;
    qrPreview.hidden = false;
    qrEmpty.hidden = true;

    try {
      const result = await uploadImage(file);
      uploadedQrUrl = result.url;
      qrPreview.src = assetUrl(result.url);
      URL.revokeObjectURL(localUrl);
      showToast("Đã tải ảnh QR", { body: "Nhớ bấm Lưu thông tin.", type: "info" });
    } catch (err) {
      showQr(uploadedQrUrl);
      qrInput.value = "";
      showToast("Tải ảnh QR thất bại", { body: err.message, type: "error" });
    }
  });

  paymentInfoForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    const message = document.getElementById("payment-info-message");
    const submitBtn = paymentInfoForm.querySelector("button[type='submit']");

    setBusy(submitBtn, true, "Đang lưu");
    try {
      await apiJson("/admin/payment-info", "PUT", {
        phone: document.getElementById("admin-phone").value.trim(),
        qr_image_url: uploadedQrUrl || "",
      });
      message.className = "message-success";
      message.textContent = "Đã lưu thông tin thanh toán";
      showToast("Đã lưu thông tin nhận tiền", { type: "success" });
    } catch (err) {
      message.className = "message-error";
      message.textContent = err.message;
    } finally {
      setBusy(submitBtn, false);
    }
  });
}

// Khởi động trang quản trị
if (dashboardBox) {
  loadRestaurants();
  loadDashboard();

  onRealtime("order_placed", (data) => {
    const when = data.is_advance && data.order_date ? ` · đặt trước cho ${data.order_date}` : "";
    showToast(data.updated ? "Có người sửa đơn" : "Có đơn mới", {
      body: `${data.employee_name} · ${data.item_count} món${when}`,
      type: "info",
    });
    loadDashboard();
  });

  onRealtime("payment_declared", (data) => {
    showToast("Có người báo đã chuyển khoản", {
      body: `${data.employee_name} · ${money(data.amount)} · cần bạn xác nhận`,
      type: "warning",
    });
    loadDashboard();
  });

  onRealtime("payment_confirmed", () => loadDashboard());

  onRealtime("order_cancelled", () => loadDashboard());
  onRealtime("order_updated", () => loadDashboard());

  connectRealtime();
}
