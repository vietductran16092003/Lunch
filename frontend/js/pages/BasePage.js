import { Navbar } from "../components/Navbar.js";
import { realtime } from "../core/RealtimeClient.js";

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
