import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";

const PAYMENT_BADGE = {
  confirmed: "completed",
  awaiting: "pending",
  unpaid: "unpaid",
  not_due: "closed",
};

const STATUS_BADGE = ["pending", "closed", "ordered", "completed"];

/** Danh sách lịch sử, mỗi đơn mở ra được bảng chi tiết hóa đơn. */
export class HistoryList {
  constructor(containerId = "history-list", { onReorder, onSelectionChange } = {}) {
    this.container = Dom.byId(containerId);
    // Trang gọi API thật; component chỉ lo hiển thị (mã 3.3 — đặt lại đơn cũ)
    this.onReorder = onReorder || (() => {});
    this.onSelectionChange = onSelectionChange || (() => {});
    this.selected = new Set();
  }

  /** Id các đơn đang chờ (pending) — chỉ nhóm này xoá được. */
  pendingIds(history) {
    return (history || []).filter((o) => o.status === "pending").map((o) => o.id);
  }

  setSelected(ids) {
    this.selected = new Set(ids);
    this.container.querySelectorAll(".history-select").forEach((box) => {
      box.checked = this.selected.has(parseInt(box.dataset.orderId, 10));
    });
    this.onSelectionChange(this.selected);
  }

  static statusClass(status) {
    return STATUS_BADGE.includes(status) ? status : "pending";
  }

  showError(message) {
    if (!this.container) return;
    this.container.setAttribute("aria-busy", "false");
    Dom.clear(this.container).appendChild(Dom.emptyState("⚠️", message));
  }

  /** key chuẩn hoá "tên món||tên quán" để so khớp với thực đơn hôm nay. */
  static itemKey(name, restaurantName) {
    return `${(name || "").trim().toLowerCase()}||${(restaurantName || "").trim().toLowerCase()}`;
  }

  /** `todayKeys`: Set các itemKey đang bán hôm nay, dùng để ẩn/hiện nút đặt lại. */
  render(history, todayKeys = null) {
    if (!this.container) return;
    this.container.setAttribute("aria-busy", "false");
    Dom.clear(this.container);

    if (!history || !history.length) {
      this.container.appendChild(Dom.emptyState("🕘", "Chưa có lịch sử đặt món."));
      return;
    }

    history.forEach((order, index) => {
      this.container.appendChild(this.buildCard(order, index, todayKeys));
    });
  }

  buildCard(order, index, todayKeys) {
    const detailId = `history-detail-${order.id}`;

    const checkbox = order.status === "pending"
      ? Dom.el("input", {
          type: "checkbox",
          class: "history-select",
          "data-order-id": order.id,
          "aria-label": `Chọn đơn ngày ${order.order_date} để xoá`,
        })
      : null;
    if (checkbox) {
      checkbox.addEventListener("click", (e) => e.stopPropagation());
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) this.selected.add(order.id);
        else this.selected.delete(order.id);
        this.onSelectionChange(this.selected);
      });
    }

    const summary = Dom.el(
      "button",
      {
        type: "button",
        class: "history-summary",
        "aria-expanded": "false",
        "aria-controls": detailId,
      },
      Dom.el("span", { class: "h-caret", "aria-hidden": "true", text: "›" }),
      Dom.el("span", { class: "h-date", text: order.order_date }),
      Dom.el("span", {
        class: `badge ${HistoryList.statusClass(order.status)}`,
        text: order.status_label || order.status,
      }),
      // Đã thanh toán chưa, và người đặt đã xác nhận nhận tiền chưa
      Dom.el("span", {
        class: `badge ${PAYMENT_BADGE[order.payment_state] || "pending"}`,
        text: order.payment_label,
      }),
      Dom.el("span", { class: "h-spacer" }),
      Dom.el("span", { class: "h-total", text: Formatter.money(order.total_cost) }),
      Dom.srOnly(`Xem chi tiết hóa đơn ngày ${order.order_date}`)
    );

    const detail = Dom.el("div", { class: "history-detail", id: detailId, hidden: true });
    detail.append(
      this.buildDetailTable(order),
      this.buildPaymentState(order),
      this.buildReorderButton(order, todayKeys)
    );

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

    const head = checkbox
      ? Dom.el("div", { class: "history-head" }, checkbox, summary)
      : summary;

    return Dom.el("article", { class: "card history-card" }, head, detail);
  }

  buildDetailTable(order) {
    const tbody = Dom.el("tbody");

    order.items.forEach((item) => {
      const name = Dom.el("td", {}, item.name);
      if (item.restaurant_name) {
        name.appendChild(
          Dom.el("div", {
            class: "subtitle",
            style: "margin:2px 0 0; font-size:12.5px;",
            text: item.restaurant_name,
          })
        );
      }
      if (item.note) {
        name.appendChild(Dom.el("div", { class: "item-note", text: item.note }));
      }

      tbody.appendChild(
        Dom.el(
          "tr",
          {},
          name,
          Dom.el("td", { class: "num mono", text: Formatter.money(item.price) }),
          Dom.el("td", { class: "num mono", text: `× ${item.quantity}` }),
          Dom.el("td", { class: "num mono", text: Formatter.money(item.line_cost) })
        )
      );
    });

    const table = Dom.el("table", {
      html:
        "<thead><tr><th scope='col'>Món ăn</th><th scope='col' class='num'>Đơn giá</th>" +
        "<th scope='col' class='num'>Số lượng</th>" +
        "<th scope='col' class='num'>Thành tiền</th></tr></thead>",
    });
    table.appendChild(tbody);

    const tfoot = Dom.el("tfoot");
    if (order.shipping_share > 0) {
      tfoot.appendChild(
        Dom.el(
          "tr",
          {},
          Dom.el("td", { colspan: "3", text: "Phí ship được chia" }),
          Dom.el("td", { class: "num mono", text: Formatter.money(order.shipping_share) })
        )
      );
    }
    tfoot.appendChild(
      Dom.el(
        "tr",
        {},
        Dom.el("td", { colspan: "3", text: "Tổng cộng" }),
        Dom.el("td", { class: "num mono", text: Formatter.money(order.total_cost) })
      )
    );
    table.appendChild(tfoot);

    return Dom.el(
      "div",
      { class: "table-wrap", style: "border:none; margin-bottom:0;" },
      table
    );
  }

  /** Luôn hiện nút, nhưng khoá lại khi không còn món nào của đơn bán ở đúng
   * quán đó hôm nay — để người dùng biết nút này tồn tại, chỉ là chưa dùng được. */
  buildReorderButton(order, todayKeys) {
    const stillAvailable = todayKeys
      ? (order.items || []).some((item) =>
          todayKeys.has(HistoryList.itemKey(item.name, item.restaurant_name))
        )
      : true;

    const button = Dom.el("button", {
      type: "button",
      class: "subtle",
      style: "margin-top:12px;",
      text: "Đặt lại cho hôm nay",
      "aria-label": `Đặt lại đơn ngày ${order.order_date} cho hôm nay`,
      disabled: !stillAvailable,
      title: stillAvailable
        ? null
        : "Hôm nay không còn món nào của đơn này ở đúng quán đó",
    });
    button.addEventListener("click", () => this.onReorder(order, button));
    return button;
  }

  buildPaymentState(order) {
    const collector = order.collector_name || "người đặt";
    const parts = [];

    if (order.paid_at) {
      parts.push(`Bạn báo đã chuyển lúc ${Formatter.moment(order.paid_at)}`);
    }
    if (order.payment_confirmed_at) {
      parts.push(
        `${collector} xác nhận nhận tiền lúc ${Formatter.moment(order.payment_confirmed_at)}`
      );
    } else if (order.paid_at) {
      parts.push(`Đang chờ ${collector} xác nhận`);
    }

    return Dom.el("div", {
      class: "pay-state",
      text: parts.length ? parts.join(" · ") : order.payment_label,
    });
  }
}
