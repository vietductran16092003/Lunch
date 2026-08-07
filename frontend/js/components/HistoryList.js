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
  constructor(containerId = "history-list", { onReorder } = {}) {
    this.container = Dom.byId(containerId);
    // Trang gọi API thật; component chỉ lo hiển thị (mã 3.3 — đặt lại đơn cũ)
    this.onReorder = onReorder || (() => {});
  }

  static statusClass(status) {
    return STATUS_BADGE.includes(status) ? status : "pending";
  }

  showError(message) {
    if (!this.container) return;
    this.container.setAttribute("aria-busy", "false");
    Dom.clear(this.container).appendChild(Dom.emptyState("⚠️", message));
  }

  render(history) {
    if (!this.container) return;
    this.container.setAttribute("aria-busy", "false");
    Dom.clear(this.container);

    if (!history || !history.length) {
      this.container.appendChild(Dom.emptyState("🕘", "Chưa có lịch sử đặt món."));
      return;
    }

    history.forEach((order, index) => {
      this.container.appendChild(this.buildCard(order, index));
    });
  }

  buildCard(order, index) {
    const detailId = `history-detail-${order.id}`;

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
      this.buildReorderButton(order)
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

    return Dom.el("article", { class: "card history-card" }, summary, detail);
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

  buildReorderButton(order) {
    const button = Dom.el("button", {
      type: "button",
      class: "subtle",
      style: "margin-top:12px;",
      text: "Đặt lại cho hôm nay",
      "aria-label": `Đặt lại đơn ngày ${order.order_date} cho hôm nay`,
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
