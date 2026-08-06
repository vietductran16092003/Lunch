// Thành phần dùng chung cho các trang xác thực: nút hiện/ẩn mật khẩu và nút Google.

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

/**
 * Bọc một ô mật khẩu bằng nút hiện/ẩn.
 * Nút nằm ngoài luồng tab mặc định của form? Không — vẫn tab tới được, và có
 * aria-pressed để trình đọc màn hình biết mật khẩu đang hiện hay ẩn.
 */
function attachPasswordToggle(input) {
  if (!input || input.dataset.toggleAttached) return;
  input.dataset.toggleAttached = "1";

  const wrap = document.createElement("span");
  wrap.className = "password-wrap";
  input.parentNode.insertBefore(wrap, input);
  wrap.appendChild(input);

  const button = document.createElement("button");
  button.type = "button";
  button.className = "password-toggle";
  button.innerHTML = EYE_OPEN;
  button.setAttribute("aria-label", "Hiện mật khẩu");
  button.setAttribute("aria-pressed", "false");

  button.addEventListener("click", () => {
    const showing = input.type === "text";
    input.type = showing ? "password" : "text";
    button.innerHTML = showing ? EYE_OPEN : EYE_OFF;
    button.setAttribute("aria-label", showing ? "Hiện mật khẩu" : "Ẩn mật khẩu");
    button.setAttribute("aria-pressed", String(!showing));
    // Giữ con trỏ ở cuối ô để người dùng gõ tiếp được ngay
    input.focus();
    const end = input.value.length;
    try { input.setSelectionRange(end, end); } catch (err) { /* type=email không hỗ trợ */ }
  });

  wrap.appendChild(button);
}

function attachAllPasswordToggles() {
  document.querySelectorAll("input[type='password']").forEach(attachPasswordToggle);
}

/** Lấy cấu hình đăng nhập (có bật Google không, domain email nào hợp lệ). */
async function loadAuthOptions() {
  try {
    const res = await fetch(`${API_BASE}/auth/options`, { credentials: "include" });
    return await res.json();
  } catch (err) {
    return { google_enabled: false, allowed_domains_label: "@fpt.com", min_password_length: 8 };
  }
}

/**
 * Dựng nút "Đăng nhập bằng Google" nếu quản trị viên đã cấu hình GOOGLE_CLIENT_ID.
 * Chưa cấu hình thì cả khối tự ẩn, phần đăng nhập bằng mật khẩu vẫn dùng bình thường.
 */
function setupGoogleSignIn(options, onError) {
  const block = document.getElementById("google-block");
  if (!block) return;

  if (!options.google_enabled) {
    block.hidden = true;
    return;
  }

  const script = document.createElement("script");
  script.src = "https://accounts.google.com/gsi/client";
  script.async = true;
  script.defer = true;

  script.onerror = () => { block.hidden = true; };

  script.onload = () => {
    if (!window.google || !window.google.accounts) {
      block.hidden = true;
      return;
    }

    window.google.accounts.id.initialize({
      client_id: options.google_client_id,
      callback: async (response) => {
        try {
          const res = await fetch(`${API_BASE}/auth/google`, {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ credential: response.credential }),
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.error || "Đăng nhập Google thất bại");
          window.location.href = "index.html";
        } catch (err) {
          onError(err.message);
        }
      },
    });

    window.google.accounts.id.renderButton(document.getElementById("google-signin-wrap"), {
      theme: "outline",
      size: "large",
      shape: "pill",
      text: "signin_with",
      locale: "vi",
      width: 320,
    });

    block.hidden = false;
  };

  document.head.appendChild(script);
}

window.attachAllPasswordToggles = attachAllPasswordToggles;
window.loadAuthOptions = loadAuthOptions;
window.setupGoogleSignIn = setupGoogleSignIn;
