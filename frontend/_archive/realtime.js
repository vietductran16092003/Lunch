// Kết nối thông báo thời gian thực.
//
// Dùng Server-Sent Events vì luồng thông báo ở đây chỉ đi một chiều
// server -> trình duyệt. Nếu sau này cần hai chiều, chỉ cần thay phần
// connect() bên dưới bằng WebSocket, phần đăng ký sự kiện giữ nguyên.

const REALTIME_RETRY_MS = 3000;
const REALTIME_MAX_RETRY_MS = 30000;

const realtimeHandlers = new Map();
let realtimeSource = null;
let realtimeRetryDelay = REALTIME_RETRY_MS;

/**
 * Đăng ký hàm xử lý cho một loại sự kiện từ server.
 * @param {string} type Ví dụ: order_placed, payment_received, orders_locked
 * @param {(data: object) => void} handler
 */
function onRealtime(type, handler) {
  if (!realtimeHandlers.has(type)) {
    realtimeHandlers.set(type, []);
  }
  realtimeHandlers.get(type).push(handler);
}

function dispatchRealtime(payload) {
  const handlers = realtimeHandlers.get(payload.type);
  if (!handlers) return;
  handlers.forEach((handler) => {
    try {
      handler(payload.data || {});
    } catch (err) {
      console.error(`Lỗi khi xử lý sự kiện ${payload.type}:`, err);
    }
  });
}

function connectRealtime() {
  if (realtimeSource || typeof EventSource === "undefined") return;

  realtimeSource = new EventSource(`${API_BASE}/stream`, { withCredentials: true });

  realtimeSource.addEventListener("open", () => {
    realtimeRetryDelay = REALTIME_RETRY_MS;
  });

  realtimeSource.addEventListener("message", (event) => {
    if (!event.data) return;
    try {
      dispatchRealtime(JSON.parse(event.data));
    } catch (err) {
      console.error("Không đọc được dữ liệu thông báo:", err);
    }
  });

  realtimeSource.addEventListener("error", () => {
    // EventSource tự thử lại, nhưng nếu server đóng hẳn thì phải tự mở lại
    if (realtimeSource && realtimeSource.readyState === EventSource.CLOSED) {
      realtimeSource = null;
      window.setTimeout(connectRealtime, realtimeRetryDelay);
      realtimeRetryDelay = Math.min(realtimeRetryDelay * 2, REALTIME_MAX_RETRY_MS);
    }
  });
}

// Ngắt kết nối khi rời trang để server không giữ luồng thừa
window.addEventListener("pagehide", () => {
  if (realtimeSource) {
    realtimeSource.close();
    realtimeSource = null;
  }
});

window.onRealtime = onRealtime;
window.connectRealtime = connectRealtime;
