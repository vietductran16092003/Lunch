import { CoordinatorSchedule } from "../components/CoordinatorSchedule.js";
import { DeadlineConfig } from "../components/DeadlineConfig.js";
import { RoleMatrix } from "../components/RoleMatrix.js";
import { Dom } from "../core/Dom.js";
import { BasePage } from "./BasePage.js";

/** Trang quản trị hệ thống: phân quyền (1.5), lịch gom đơn (1.6), giờ chốt (4.1). */
export class SettingsPage extends BasePage {
  async init() {
    const isAdmin = Boolean(this.user && this.user.is_admin);

    if (!isAdmin) {
      // Không chặn cứng bằng redirect: giải thích rõ vì sao không vào được
      const main = Dom.byId("main");
      Dom.clear(main).append(
        Dom.el("h1", { text: "Quản trị hệ thống" }),
        Dom.notice(
          "warning",
          "Bạn không có quyền vào khu vực này",
          "Trang này chỉ dành cho người mang vai trò Quản trị. Liên hệ quản trị viên nếu bạn cần quyền."
        ),
        Dom.el("a", { class: "link-action", href: "index.html", text: "← Về trang thực đơn" })
      );
      return;
    }

    this.deadline = new DeadlineConfig({ canEdit: true });
    this.roles = new RoleMatrix("role-matrix", { currentUserId: this.user.id });
    this.schedule = new CoordinatorSchedule("schedule-list", { canEdit: true });

    await this.deadline.load();
    await this.roles.load();
    // Lịch cần biết ai mang vai trò coordinator nên nạp sau ma trận phân quyền
    await this.schedule.load();

    // Đổi vai trò xong thì danh sách ứng viên gom đơn cũng đổi theo
    this.listen({
      roles_updated: () => {
        this.roles.load();
        this.schedule.load();
      },
      deadline_updated: () => this.deadline.load(),
    });
  }
}
