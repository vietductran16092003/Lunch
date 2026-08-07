import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";

/** Danh sách người còn nợ tiền — đơn đã chốt nhưng chưa xác nhận thanh toán (mã 5.6). */
export class DebtsTable {
  constructor(containerId = "debts-box") {
    this.container = Dom.byId(containerId);
  }

  showError(message) {
    if (!this.container) return;
    this.container.setAttribute("aria-busy", "false");
    Dom.clear(this.container).appendChild(Dom.emptyState("⚠️", message));
  }

  render(data) {
    if (!this.container) return;
    this.container.setAttribute("aria-busy", "false");
    Dom.clear(this.container);

    if (!data.debts || !data.debts.length) {
      this.container.appendChild(
        Dom.emptyState("✓", "Không ai còn nợ tiền — mọi đơn đã được xác nhận thanh toán.")
      );
      return;
    }

    const tbody = Dom.el("tbody");
    data.debts.forEach((debt) => {
      const orderList = debt.orders.map((o) => `${o.order_date} (${Formatter.money(o.amount)})`);
      tbody.appendChild(
        Dom.el(
          "tr",
          {},
          Dom.el("td", { text: debt.user_name }),
          Dom.el("td", { text: orderList.join(", ") }),
          Dom.el("td", { class: "num mono", text: Formatter.money(debt.total_owed) })
        )
      );
    });

    const table = Dom.el("table", {
      html:
        "<caption>Người còn nợ, sắp xếp theo số tiền giảm dần</caption>" +
        "<thead><tr><th scope='col'>Nhân viên</th><th scope='col'>Đơn chưa thanh toán</th>" +
        "<th scope='col' class='num'>Tổng nợ</th></tr></thead>",
    });
    table.appendChild(tbody);
    table.appendChild(
      Dom.el(
        "tfoot",
        {},
        Dom.el(
          "tr",
          {},
          Dom.el("td", { colspan: "2", text: "Tổng cộng" }),
          Dom.el("td", { class: "num mono", text: Formatter.money(data.grand_total) })
        )
      )
    );

    this.container.appendChild(Dom.el("div", { class: "table-wrap" }, table));
  }
}
