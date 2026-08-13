import { Chatbot } from "../components/Chatbot.js";
import { Navbar } from "../components/Navbar.js";
import { realtime } from "../core/RealtimeClient.js";
import { toasts } from "../core/ToastManager.js";

/** Khung chung cho mọi trang có thanh điều hướng. */
export class BasePage {
  /** Đặt true ở lớp con nếu trang cần thanh điều hướng. */
  static usesNavbar = true;

  constructor() {
    this.realtime = realtime;
    this.user = null;
  }

  async start() {
    if (this.constructor.usesNavbar) {
      this.navbar = new Navbar();
      this.user = await this.navbar.render();
      // render() chuyển hướng sang login khi chưa đăng nhập
      if (!this.user) return;
      new Chatbot().mount();
      // Thông báo chung — luôn lắng nghe bất kể trang có gọi listen() hay không.
      // NotificationBell tự tải lại danh sách khi có sự kiện này; đây chỉ lo hiện toast,
      // và phải tự lọc vì server phát cho MỌI trình duyệt, không riêng người liên quan.
      realtime.on("notification_created", (data) => {
        const forEveryone = !data.target_user_id && !data.target_role;
        const forMe = data.target_user_id === this.user.id
          || (data.target_role && this.user.roles.includes(data.target_role));
        if (forEveryone || forMe) toasts.info(data.title, data.message);
      });
      realtime.connect();
    }
    await this.init();
  }

  /** Lớp con cài đặt phần khởi tạo riêng của trang. */
  async init() {}

  /** Đăng ký các sự kiện thời gian thực rồi mở kết nối. */
  listen(handlers) {
    Object.entries(handlers).forEach(([type, handler]) => this.realtime.on(type, handler));
    this.realtime.connect();
  }
}
