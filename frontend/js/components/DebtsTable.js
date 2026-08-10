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

    this.container.append(
      Dom.el(
        "div",
        { class: "debts-total" },
        Dom.el("span", { text: `${data.debts.length} người còn nợ` }),
        Dom.el("strong", { class: "mono", text: Formatter.money(data.grand_total) })
      ),
      Dom.el(
        "div",
        { class: "debts-list" },
        ...data.debts.map((debt) => this.buildDebtCard(debt))
      )
    );
  }

  buildDebtCard(debt) {
    return Dom.el(
      "div",
      { class: "debt-card" },
      Dom.el(
        "div",
        { class: "debt-card-head" },
        Dom.el("span", { class: "debt-name", text: debt.user_name }),
        Dom.el("strong", { class: "mono", text: Formatter.money(debt.total_owed) })
      ),
      Dom.el(
        "div",
        { class: "debt-orders" },
        ...debt.orders.map((o) =>
          Dom.el("span", {
            class: "debt-order-pill",
            text: `${o.order_date} · ${Formatter.money(o.amount)}`,
          })
        )
      )
    );
  }
}
