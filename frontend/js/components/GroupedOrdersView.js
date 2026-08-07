import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";

/** Tổng hợp đơn theo quán (mã 4.2), kèm ghi chú món để dặn quán. */
export class GroupedOrdersView {
  constructor(containerId = "grouped-box") {
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

    if (!data.restaurants || !data.restaurants.length) {
      this.container.appendChild(
        Dom.emptyState("📋", "Chưa có ai đặt món trong ngày này.")
      );
      return;
    }

    data.restaurants.forEach((restaurant) => {
      this.container.appendChild(this.buildRestaurantCard(restaurant));
    });

    this.container.appendChild(
      Dom.el(
        "p",
        { class: "subtitle", style: "text-align:right; font-weight:600;" },
        `Tổng cộng: ${Formatter.money(data.grand_total)}`
      )
    );
  }

  buildRestaurantCard(restaurant) {
    const tbody = Dom.el("tbody");

    restaurant.items.forEach((item) => {
      const name = Dom.el("td", {}, item.name);
      (item.notes || []).forEach((note) => {
        name.appendChild(Dom.el("div", { class: "item-note", text: note }));
      });

      tbody.appendChild(
        Dom.el(
          "tr",
          {},
          name,
          Dom.el("td", { class: "num mono", text: Formatter.money(item.price) }),
          Dom.el("td", { class: "num mono", text: String(item.total_quantity) }),
          Dom.el("td", {
            class: "num mono",
            text: Formatter.money(item.price * item.total_quantity),
          })
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
    table.appendChild(
      Dom.el(
        "tfoot",
        {},
        Dom.el(
          "tr",
          {},
          Dom.el("td", { colspan: "3", text: "Tổng quán" }),
          Dom.el("td", { class: "num mono", text: Formatter.money(restaurant.subtotal) })
        )
      )
    );

    const head = Dom.el(
      "div",
      { class: "card-head" },
      Dom.el("h3", { style: "margin:0;", text: restaurant.restaurant_name || "Không rõ quán" })
    );

    if (restaurant.grab_url) {
      head.appendChild(
        Dom.el("a", {
          href: restaurant.grab_url,
          target: "_blank",
          rel: "noopener noreferrer",
          class: "link-action",
          text: "Mở Grab",
        })
      );
    }

    return Dom.el(
      "div",
      { class: "card" },
      head,
      Dom.el("div", { class: "table-wrap", style: "margin:12px 0 0;" }, table)
    );
  }
}
