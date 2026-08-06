import { API_BASE } from "./config.js";

/**
 * Kết nối thông báo thời gian thực.
 *
 * Dùng Server-Sent Events vì luồng chỉ đi một chiều server -> trình duyệt.
 * Muốn đổi sang WebSocket thì chỉ phải sửa connect() ở đây, phần đăng ký sự
 * kiện của các trang giữ nguyên.
 */
export class RealtimeClient {
  static RETRY_MS = 3000;
  static MAX_RETRY_MS = 30000;

  constructor(url = `${API_BASE}/stream`) {
    this.url = url;
    this.handlers = new Map();
    this.source = null;
    this.retryDelay = RealtimeClient.RETRY_MS;

    // Ngắt kết nối khi rời trang để server không giữ luồng thừa
    window.addEventListener("pagehide", () => this.disconnect());
  }

  /** Đăng ký hàm xử lý cho một loại sự kiện (order_placed, payment_declared, ...). */
  on(type, handler) {
    if (!this.handlers.has(type)) this.handlers.set(type, []);
    this.handlers.get(type).push(handler);
    return this;
  }

  connect() {
    if (this.source || typeof EventSource === "undefined") return;

    this.source = new EventSource(this.url, { withCredentials: true });

    this.source.addEventListener("open", () => {
      this.retryDelay = RealtimeClient.RETRY_MS;
    });

    this.source.addEventListener("message", (event) => {
      if (!event.data) return;
      try {
        this.dispatch(JSON.parse(event.data));
      } catch (err) {
        console.error("Không đọc được dữ liệu thông báo:", err);
      }
    });

    this.source.addEventListener("error", () => {
      // EventSource tự thử lại, nhưng server đóng hẳn thì phải tự mở lại
      if (this.source && this.source.readyState === EventSource.CLOSED) {
        this.source = null;
        window.setTimeout(() => this.connect(), this.retryDelay);
        this.retryDelay = Math.min(this.retryDelay * 2, RealtimeClient.MAX_RETRY_MS);
      }
    });
  }

  disconnect() {
    if (this.source) {
      this.source.close();
      this.source = null;
    }
  }

  dispatch(payload) {
    const handlers = this.handlers.get(payload.type);
    if (!handlers) return;
    handlers.forEach((handler) => {
      try {
        handler(payload.data || {});
      } catch (err) {
        console.error(`Lỗi khi xử lý sự kiện ${payload.type}:`, err);
      }
    });
  }

  get readyState() {
    return this.source ? this.source.readyState : null;
  }
}

export const realtime = new RealtimeClient();
