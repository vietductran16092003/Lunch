import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";

/** Sổ đối soát: mỗi dòng nạp/rút, không sửa/xoá được sau khi ghi (mã 5.4). */
export class FundLedger {
  constructor(containerId = "ledger-box") {
    this.container = Dom.byId(containerId);
  }

  showError(message) {
    if (!this.container) return;
    this.container.setAttribute("aria-busy", "false");
    Dom.clear(this.container).appendChild(Dom.emptyState("⚠️", message));
  }

  render(transactions) {
    if (!this.container) return;
    this.container.setAttribute("aria-busy", "false");
    Dom.clear(this.container);

    if (!transactions || !transactions.length) {
      this.container.appendChild(Dom.emptyState("📒", "Chưa có giao dịch nào."));
      return;
    }

    const tbody = Dom.el("tbody");
    transactions.forEach((tx) => {
      const isTopup = tx.type === "topup";
      tbody.appendChild(
        Dom.el(
          "tr",
          {},
          Dom.el("td", { class: "mono", text: Formatter.moment(tx.created_at) }),
          Dom.el(
            "td",
            {},
            Dom.el("span", {
              class: `badge ${isTopup ? "completed" : "unpaid"}`,
              text: isTopup ? "Nạp" : "Rút",
            })
          ),
          Dom.el("td", { text: tx.user_name || "—" }),
          Dom.el("td", { text: tx.note || "—" }),
          Dom.el("td", {
            class: "num mono",
            text: `${isTopup ? "+" : "−"}${Formatter.money(tx.amount)}`,
          })
        )
      );
    });

    const table = Dom.el("table", {
      html:
        "<caption>Sổ đối soát thu chi</caption>" +
        "<thead><tr><th scope='col'>Thời điểm</th><th scope='col'>Loại</th>" +
        "<th scope='col'>Người thực hiện</th><th scope='col'>Ghi chú</th>" +
        "<th scope='col' class='num'>Số tiền</th></tr></thead>",
    });
    table.appendChild(tbody);
    this.container.appendChild(Dom.el("div", { class: "table-wrap" }, table));
  }
}
