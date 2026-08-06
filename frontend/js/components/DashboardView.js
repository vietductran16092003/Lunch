import { API_BASE } from "../core/config.js";
import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";
import { toasts } from "../core/ToastManager.js";

const STATUS_BADGE = ["pending", "closed", "ordered", "completed"];

/** Bảng điều khiển gộp: tổng hợp theo món + chi tiết theo nhân viên. */
export class DashboardView {
  constructor({ onConfirmPayment } = {}) {
    this.box = Dom.byId("dashboard-box");
    this.stats = Dom.byId("dashboard-stats");
    this.onConfirmPayment = onConfirmPayment || (() => {});
  }

  static statusClass(status) {
    return STATUS_BADGE.includes(status) ? status : "pending";
  }

  showError(onRetry) {
    if (!this.box) return;
    this.box.setAttribute("aria-busy", "false");
    const retry = Dom.el("button", { type: "button", text: "Thử lại" });
    retry.addEventListener("click", onRetry);
    Dom.clear(this.box).appendChild(
      Dom.emptyState("⚠️", "Không tải được bảng điều khiển. ", retry)
    );
  }

  render(data) {
    if (!this.box) return;
    this.box.setAttribute("aria-busy", "false");
    Dom.clear(this.box);

    this.renderHeader(data);
    this.renderStats(data);

    if (!data.employees.length) {
      this.box.appendChild(Dom.emptyState("📋", "Chưa có nhân viên nào đặt món hôm nay."));
      return;
    }

    this.box.append(
      this.buildSummaryTable(data),
      this.buildEmployeeTable(data),
      Dom.el("p", {
        class: "note",
        text: 'Cột "Thanh toán" chỉ hiện sau khi đơn đã chốt — trước đó nhân viên vẫn có thể đổi ý.',
      })
    );
  }

  renderHeader(data) {
    Dom.setText("dashboard-total", Formatter.money(data.totals.grand_total));
    Dom.setText(
      "dashboard-heading",
      data.is_today
        ? "3. Bảng điều khiển đơn hôm nay"
        : `3. Bảng điều khiển đơn ${Formatter.dayLabel(data.date, data.today).toLowerCase()} (${data.date})`
    );

    const lockBtn = Dom.byId("lock-orders-btn");
    if (lockBtn) {
      lockBtn.disabled = data.locked || data.totals.employee_count === 0;
      lockBtn.textContent = data.locked ? "Đơn đã chốt" : "Chốt đơn & đặt trên Grab";
    }

    const exportLink = Dom.byId("export-link");
    if (exportLink) exportLink.href = `${API_BASE}/admin/orders/export?date=${data.date}`;
  }

  renderStats(data) {
    if (!this.stats) return;
    Dom.clear(this.stats);

    [
      { label: "Nhân viên đã đặt", value: data.totals.employee_count },
      { label: "Tổng số phần", value: data.totals.item_count },
      { label: "Đã nhận tiền", value: `${data.totals.paid_count}/${data.totals.employee_count}` },
      {
        label: "Chờ xác nhận",
        value: data.totals.awaiting_count,
        accent: data.totals.awaiting_count > 0,
      },
    ].forEach((item) => {
      this.stats.appendChild(
        Dom.el(
          "div",
          { class: `stat${item.accent ? " is-accent" : ""}` },
          Dom.el("div", { class: "stat-label", text: item.label }),
          Dom.el("div", { class: "stat-value", text: String(item.value) })
        )
      );
    });
  }

  buildSummaryTable(data) {
    const tbody = Dom.el("tbody");

    data.summary.forEach((row) => {
      tbody.appendChild(
        Dom.el(
          "tr",
          {},
          Dom.el("td", { text: row.restaurant_name || "—" }),
          Dom.el("td", { text: row.item_name }),
          Dom.el("td", { class: "num", text: Formatter.money(row.price) }),
          Dom.el("td", { class: "num", text: String(row.total_quantity) }),
          Dom.el("td", { class: "num", text: Formatter.money(row.price * row.total_quantity) })
        )
      );
    });

    const table = Dom.el("table", {
      html:
        "<caption>Tổng hợp theo món — dùng bảng này để đặt trên Grab</caption>" +
        "<thead><tr><th scope='col'>Nhà hàng</th><th scope='col'>Món ăn</th>" +
        "<th scope='col' class='num'>Đơn giá</th><th scope='col' class='num'>Số phần</th>" +
        "<th scope='col' class='num'>Thành tiền</th></tr></thead>",
    });
    table.appendChild(tbody);
    return Dom.el("div", { class: "table-wrap" }, table);
  }

  buildEmployeeTable(data) {
    const tbody = Dom.el("tbody");
    data.employees.forEach((emp) => tbody.appendChild(this.buildEmployeeRow(emp)));

    const table = Dom.el("table", {
      html:
        "<caption>Chi tiết theo nhân viên — dùng bảng này để thu tiền</caption>" +
        "<thead><tr><th scope='col'>Nhân viên</th><th scope='col'>Món đã đặt</th>" +
        "<th scope='col' class='num'>Thành tiền</th><th scope='col'>Trạng thái</th>" +
        "<th scope='col'>Thanh toán</th></tr></thead>",
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
          Dom.el("td", { class: "num mono", text: Formatter.money(data.totals.grand_total) }),
          Dom.el("td", { colspan: "2" })
        )
      )
    );

    return Dom.el("div", { class: "table-wrap" }, table);
  }

  buildEmployeeRow(emp) {
    return Dom.el(
      "tr",
      {},
      Dom.el("td", { text: emp.employee_name }),
      Dom.el("td", {
        text: emp.items.map((i) => `${i.item_name} × ${i.quantity}`).join(", "),
      }),
      Dom.el("td", { class: "num mono", text: Formatter.money(emp.total_cost) }),
      Dom.el(
        "td",
        {},
        Dom.el("span", {
          class: `badge ${DashboardView.statusClass(emp.status)}`,
          text: emp.status_label,
        })
      ),
      this.buildPaymentCell(emp)
    );
  }

  buildPaymentCell(emp) {
    if (emp.confirmed) {
      return Dom.el(
        "td",
        {},
        Dom.el("span", { class: "badge completed", text: "Đã nhận tiền" })
      );
    }

    if (emp.status === "pending") {
      return Dom.el("td", { style: "color: var(--text-secondary);", text: "Chưa chốt" });
    }

    // Đã chốt đơn thì xác nhận được, kể cả khi nhân viên chưa bấm báo
    const confirm = Dom.el("button", {
      type: "button",
      class: emp.awaiting_confirmation ? "" : "ghost",
      text: "Đã nhận tiền",
      "aria-label":
        `Xác nhận đã nhận tiền của ${emp.employee_name}, ${Formatter.money(emp.total_cost)}`,
    });
    confirm.addEventListener("click", () => this.confirmPayment(emp, confirm));

    return Dom.el(
      "td",
      {},
      Dom.el(
        "div",
        { style: "display:flex; flex-direction:column; gap:6px; align-items:flex-start;" },
        Dom.el("span", {
          class: `badge ${emp.awaiting_confirmation ? "pending" : "unpaid"}`,
          text: emp.awaiting_confirmation ? "Báo đã chuyển" : "Chưa chuyển",
        }),
        confirm
      )
    );
  }

  async confirmPayment(emp, button) {
    Dom.setBusy(button, true, "Đang xác nhận");
    try {
      await api.post(`/admin/orders/${emp.order_id}/confirm-payment`);
      toasts.success(
        "Đã xác nhận nhận tiền",
        `${emp.employee_name} · ${Formatter.money(emp.total_cost)}`
      );
      await this.onConfirmPayment();
    } catch (err) {
      Dom.setBusy(button, false);
      toasts.error("Xác nhận thất bại", err.message);
    }
  }
}
