import { DebtsTable } from "../components/DebtsTable.js";
import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";
import { hasAnyRole } from "../core/roles.js";
import { toasts } from "../core/ToastManager.js";
import { BasePage } from "./BasePage.js";

const TYPE_LABELS = {
  topup: "Ghi vào quỹ",
  withdraw: "Ghi vào quỹ",
  dues: "Ghi nhận góp quỹ",
};

/** Trang thủ quỹ: số dư, quản lý quỹ (nạp/rút/trả đơn/góp tháng gộp chung
 * một form), theo dõi nợ, báo cáo chi tiết (mã 5.3–5.6). */
export class TreasuryPage extends BasePage {
  constructor() {
    super();
    this.debts = new DebtsTable();
  }

  async init() {
    if (!hasAnyRole(this.user, ["treasurer", "admin"])) {
      const main = Dom.byId("main");
      Dom.clear(main).append(
        Dom.el("h1", { text: "Quỹ chung" }),
        Dom.notice(
          "warning",
          "Bạn không có quyền vào khu vực này",
          "Trang này dành cho người mang vai trò Thủ quỹ. Liên hệ quản trị viên nếu bạn cần quyền."
        ),
        Dom.el("a", { class: "link-action", href: "index.html", text: "← Về trang thực đơn" })
      );
      return;
    }

    // Admin (không mang vai trò thủ quỹ) chỉ xem, không thao tác được quỹ
    this.isTreasurer = hasAnyRole(this.user, ["treasurer"]);
    Dom.byId("fund-manage-panel").hidden = !this.isTreasurer;

    Dom.byId("report-form").addEventListener("submit", (e) => this.loadReport(e));
    const today = Formatter.todayIso();
    Dom.byId("report-start").value = today;
    Dom.byId("report-end").value = today;

    const loaders = [this.loadBalance(), this.loadDebts()];

    if (this.isTreasurer) {
      Dom.byId("fund-type").addEventListener("change", () => this.updateFormFields());
      Dom.byId("fund-form").addEventListener("submit", (e) => this.submitFundForm(e));
      Dom.byId("pay-fund-btn").addEventListener("click", () => this.payFromFund());
      Dom.byId("dues-month").addEventListener("change", () => this.loadDuesOverview());

      Dom.byId("pay-fund-date").value = today;
      this.currentMonth = today.slice(0, 7);
      Dom.byId("dues-month").value = this.currentMonth;
      this.updateFormFields();
      loaders.push(this.loadDuesEmployees());
    }

    await Promise.all(loaders);

    this.listen({
      fund_updated: () => {
        this.loadBalance();
        if (this.isTreasurer) this.loadDuesOverview();
      },
      payment_confirmed: () => this.loadDebts(),
      payment_declared: () => this.loadDebts(),
      shipping_split: () => this.loadDebts(),
    });
  }

  async loadBalance() {
    try {
      const data = await api.get("/fund/balance");
      this.renderStats(data.balance);
    } catch (err) {
      toasts.error("Không tải được số dư quỹ", err.message);
    }
  }

  renderStats(balance) {
    const box = Dom.byId("fund-stats");
    Dom.clear(box).appendChild(
      Dom.el(
        "div",
        { class: "stat is-accent" },
        Dom.el("div", { class: "stat-label", text: "Số dư quỹ hiện tại" }),
        Dom.el("div", { class: "stat-value", text: Formatter.money(balance) })
      )
    );
  }

  async loadDebts() {
    try {
      const data = await api.get("/fund/debts");
      this.debts.render(data);
    } catch (err) {
      this.debts.showError(err.message);
    }
  }

  // ===== Form quản lý quỹ gộp chung (nạp/rút/trả đơn/góp tháng) =====

  updateFormFields() {
    const type = Dom.byId("fund-type").value;
    Dom.byId("fund-note-field").hidden = type !== "topup" && type !== "withdraw";
    Dom.byId("dues-month-field").hidden = type !== "dues";
    Dom.byId("dues-employee-field").hidden = type !== "dues";
    Dom.byId("dues-overview-box").hidden = type !== "dues";
    Dom.byId("pay-fund-panel").hidden = type !== "dues";
    Dom.byId("fund-submit-btn").textContent = TYPE_LABELS[type];

    if (type === "dues") this.loadDuesOverview();
  }

  async submitFundForm(event) {
    event.preventDefault();
    const type = Dom.byId("fund-type").value;
    if (type === "topup" || type === "withdraw") return this.submitTransaction(type);
    if (type === "dues") return this.submitDues();
  }

  async submitTransaction(type) {
    const amountInput = Dom.byId("fund-amount");
    const noteInput = Dom.byId("fund-note");
    const message = Dom.byId("fund-form-message");
    const button = Dom.byId("fund-submit-btn");

    amountInput.removeAttribute("aria-invalid");
    const amount = parseInt(amountInput.value, 10);
    if (!amount || amount <= 0) {
      amountInput.setAttribute("aria-invalid", "true");
      Dom.setText("fund-amount-error", "Vui lòng nhập số tiền lớn hơn 0");
      amountInput.focus();
      return;
    }
    Dom.setText("fund-amount-error", "");

    const verb = type === "topup" ? "nạp" : "rút";
    if (!window.confirm(`Xác nhận ${verb} ${Formatter.money(amount)} vào quỹ chung?`)) return;

    Dom.setBusy(button, true, "Đang ghi vào quỹ");
    try {
      const endpoint = type === "topup" ? "/fund/topup" : "/fund/withdraw";
      await api.post(endpoint, { amount, note: noteInput.value.trim() });

      message.className = "message-success";
      message.textContent = `Đã ${verb} ${Formatter.money(amount)} vào quỹ.`;
      toasts.success("Đã ghi vào quỹ", message.textContent);

      amountInput.value = "";
      noteInput.value = "";
      await this.loadBalance();
    } catch (err) {
      message.className = "message-error";
      message.textContent = err.message;
      toasts.error(`${type === "topup" ? "Nạp" : "Rút"} quỹ thất bại`, err.message);
    } finally {
      Dom.setBusy(button, false);
    }
  }

  async payFromFund() {
    const dateInput = Dom.byId("pay-fund-date");
    const message = Dom.byId("fund-form-message");
    const button = Dom.byId("pay-fund-btn");

    if (!dateInput.value) return;
    if (!window.confirm(`Trả toàn bộ đơn chưa thanh toán ngày ${dateInput.value} bằng quỹ chung?`)) {
      return;
    }

    Dom.setBusy(button, true, "Đang trả bằng quỹ");
    try {
      const result = await api.post("/fund/pay-from-fund", { date: dateInput.value });
      message.className = "message-success";
      message.textContent =
        `Đã trả ${result.order_count} đơn, tổng ${Formatter.money(result.total_paid)}.`;
      toasts.success("Đã thanh toán bằng quỹ", message.textContent);
      await Promise.all([this.loadBalance(), this.loadDebts()]);
    } catch (err) {
      message.className = "message-error";
      message.textContent = err.message;
      toasts.error("Thanh toán bằng quỹ thất bại", err.message);
    } finally {
      Dom.setBusy(button, false);
    }
  }

  async loadDuesEmployees() {
    const select = Dom.byId("dues-employee");
    if (!select) return;
    try {
      const data = await api.get("/coordinator/employees");
      Dom.clear(select);
      select.appendChild(Dom.el("option", { value: "", text: "— Chọn nhân viên —" }));
      (data.users || []).forEach((u) => {
        select.appendChild(Dom.el("option", { value: u.id, text: `${u.name} (${u.email})` }));
      });
    } catch (err) {
      // Không chặn trang nếu chưa tải được danh sách, form vẫn hiện
    }
  }

  async loadDuesOverview() {
    const box = Dom.byId("dues-overview-box");
    if (!box || box.hidden) return;
    const month = Dom.byId("dues-month").value || this.currentMonth;
    try {
      const data = await api.get(`/fund/dues?month=${encodeURIComponent(month)}`);
      Dom.clear(box);

      box.appendChild(
        Dom.el("p", { style: "margin:0 0 8px;" },
          Dom.el("strong", { text: `Tháng ${month}: ` }),
          `đã thu ${Formatter.money(data.total_collected)}`
        )
      );

      if (data.contributed.length) {
        box.appendChild(
          Dom.el(
            "ul",
            { style: "margin:0 0 8px; padding-left:18px;" },
            ...data.contributed.map((c) =>
              Dom.el("li", { text: `${c.user_name}: ${Formatter.money(c.amount)}` })
            )
          )
        );
      }

      if (data.pending.length) {
        box.appendChild(
          Dom.el("p", { style: "margin:0;" },
            Dom.el("strong", { text: "Chưa góp: " }),
            data.pending.map((u) => u.name).join(", ")
          )
        );
      } else {
        box.appendChild(Dom.el("p", { style: "margin:0;", text: "Mọi người đã góp đủ tháng này." }));
      }
    } catch (err) {
      Dom.clear(box).appendChild(Dom.emptyState("⚠️", "Không tải được tình hình góp quỹ."));
    }
  }

  async submitDues() {
    const month = Dom.byId("dues-month").value;
    const employeeSelect = Dom.byId("dues-employee");
    const message = Dom.byId("fund-form-message");
    const button = Dom.byId("fund-submit-btn");
    const amountInput = Dom.byId("fund-amount");

    if (!month || !employeeSelect.value || !amountInput.value) {
      message.className = "message-error";
      message.textContent = "Vui lòng chọn tháng, nhân viên và nhập số tiền";
      return;
    }

    Dom.setBusy(button, true, "Đang ghi nhận");
    try {
      await api.post("/fund/dues", {
        user_id: parseInt(employeeSelect.value, 10),
        amount: parseInt(amountInput.value, 10),
        month,
      });
      message.className = "message-success";
      message.textContent = "Đã ghi nhận góp quỹ";
      toasts.success("Đã ghi nhận góp quỹ",
        `${employeeSelect.options[employeeSelect.selectedIndex].text} · ${Formatter.money(amountInput.value)}`);
      amountInput.value = "";
      employeeSelect.value = "";
      await this.loadDuesOverview();
    } catch (err) {
      message.className = "message-error";
      message.textContent = err.message;
      toasts.error("Ghi nhận thất bại", err.message);
    } finally {
      Dom.setBusy(button, false);
    }
  }

  // ===== Báo cáo chi tiết (gộp sổ đối soát + báo cáo AI theo khoảng ngày) =====

  async loadReport(event) {
    event.preventDefault();
    const start = Dom.byId("report-start").value;
    const end = Dom.byId("report-end").value;
    const box = Dom.byId("report-box");
    const button = event.target.querySelector("button[type='submit']");

    if (!start || !end) return;

    Dom.setBusy(button, true, "Đang tính báo cáo");
    try {
      const data = await api.get(
        `/ai/report?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
      );
      Dom.clear(box);

      const rows = data.daily_totals.map((d) =>
        Dom.el(
          "tr", {},
          Dom.el("td", { text: d.date }),
          Dom.el("td", { class: "num mono", text: Formatter.money(d.total) })
        )
      );
      const table = rows.length
        ? Dom.el(
            "table",
            { html: "<thead><tr><th scope='col'>Ngày</th><th scope='col' class='num'>Tổng chi</th></tr></thead>" },
          )
        : null;
      if (table) {
        const tbody = Dom.el("tbody");
        rows.forEach((r) => tbody.appendChild(r));
        table.appendChild(tbody);
      }

      box.append(
        Dom.el("p", { style: "margin:0 0 12px;", text: data.report_text }),
        table ? Dom.el("div", { class: "table-wrap" }, table) : null
      );
    } catch (err) {
      Dom.clear(box).appendChild(Dom.emptyState("⚠️", err.message));
    } finally {
      Dom.setBusy(button, false);
    }
  }
}
