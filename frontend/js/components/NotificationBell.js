import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";
import { realtime } from "../core/RealtimeClient.js";

/** Chuông thông báo trên navbar: danh sách lưu lại (không chỉ toast thoáng qua). */
export class NotificationBell {
  constructor(containerId = "notification-bell") {
    this.container = Dom.byId(containerId);
    this.items = [];
    this.unreadCount = 0;
  }

  mount() {
    if (!this.container) return;
    this.build();
    this.bind();
    this.load();
    realtime.on("notification_created", () => this.load());
  }

  build() {
    Dom.clear(this.container);
    this.container.append(
      Dom.el(
        "button",
        {
          type: "button",
          class: "bell-trigger",
          id: "bell-trigger",
          "aria-haspopup": "true",
          "aria-expanded": "false",
          "aria-label": "Thông báo",
        },
        Dom.el("span", { "aria-hidden": "true", text: "🔔" }),
        Dom.el("span", { class: "bell-badge", id: "bell-badge", hidden: true })
      ),
      Dom.el("div", { class: "bell-dropdown", id: "bell-dropdown", hidden: true })
    );
  }

  bind() {
    const trigger = Dom.byId("bell-trigger");
    const close = () => {
      this.container.classList.remove("is-open");
      trigger.setAttribute("aria-expanded", "false");
    };
    trigger.addEventListener("click", () => {
      const open = this.container.classList.toggle("is-open");
      trigger.setAttribute("aria-expanded", String(open));
      if (open) this.load();
    });
    document.addEventListener("click", (e) => {
      if (!this.container.contains(e.target)) close();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") close();
    });
  }

  async load() {
    try {
      const data = await api.get("/notifications?limit=20");
      this.items = data.notifications || [];
      this.unreadCount = data.unread_count || 0;
      this.renderBadge();
      this.renderList();
    } catch (err) {
      // Chuông không tải được thì im lặng, không chặn cả trang
    }
  }

  renderBadge() {
    const badge = Dom.byId("bell-badge");
    if (!badge) return;
    if (this.unreadCount > 0) {
      badge.hidden = false;
      badge.textContent = this.unreadCount > 9 ? "9+" : String(this.unreadCount);
    } else {
      badge.hidden = true;
    }
  }

  renderList() {
    const box = Dom.byId("bell-dropdown");
    if (!box) return;
    Dom.clear(box);

    const header = Dom.el(
      "div",
      { class: "bell-dropdown-head" },
      Dom.el("span", { text: "Thông báo" }),
      Dom.el("button", { type: "button", class: "link-action", text: "Đánh dấu tất cả đã đọc" })
    );
    header.querySelector("button").addEventListener("click", () => this.markAllRead());
    box.appendChild(header);

    if (!this.items.length) {
      box.appendChild(Dom.emptyState("🔔", "Chưa có thông báo nào."));
      return;
    }

    const list = Dom.el("div", { class: "bell-list" });
    this.items.forEach((n) => list.appendChild(this.buildItem(n)));
    box.appendChild(list);
  }

  buildItem(notification) {
    const item = Dom.el(
      "button",
      {
        type: "button",
        class: `bell-item${notification.is_read ? "" : " is-unread"}`,
      },
      Dom.el(
        "div",
        { class: "bell-item-title" },
        Dom.el("span", { "aria-hidden": "true", text: "🔔 " }),
        document.createTextNode(notification.title)
      ),
      notification.message ? Dom.el("div", { class: "bell-item-message", text: notification.message }) : null,
      Dom.el("div", { class: "bell-item-time", text: Formatter.moment(notification.created_at) })
    );
    item.addEventListener("click", () => this.markRead(notification, item));
    return item;
  }

  async markRead(notification, item) {
    if (notification.is_read) return;
    notification.is_read = true;
    item.classList.remove("is-unread");
    this.unreadCount = Math.max(0, this.unreadCount - 1);
    this.renderBadge();
    try {
      await api.post(`/notifications/${notification.id}/read`, {});
    } catch (err) {
      // Lỡ lưu thất bại thì lần load kế tiếp sẽ tự sửa lại số đếm
    }
  }

  async markAllRead() {
    this.items.forEach((n) => { n.is_read = true; });
    this.unreadCount = 0;
    this.renderBadge();
    this.renderList();
    try {
      await api.post("/notifications/read-all", {});
    } catch (err) {
      // Tương tự — lần load kế tiếp sẽ đồng bộ lại
    }
  }
}
