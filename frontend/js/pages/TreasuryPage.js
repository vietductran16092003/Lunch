import { DebtsTable } from "../components/DebtsTable.js";
import { FundLedger } from "../components/FundLedger.js";
import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";
import { hasAnyRole } from "../core/roles.js";
import { toasts } from "../core/ToastManager.js";
import { BasePage } from "./BasePage.js";

/** Trang thủ quỹ: số dư, nạp/rút, sổ đối soát, theo dõi nợ (mã 5.3–5.6). */
export class TreasuryPage extends BasePage {
  constructor() {
    super();
    this.ledger = new FundLedger();
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

    Dom.byId("fund-form").addEventListener("submit", (e) => this.submitTransaction(e));

    await Promise.all([this.loadBalance(), this.loadDebts(), this.loadLedger()]);

    this.listen({
      fund_updated: () => {
        this.loadBalance();
        this.loadLedger();
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

  async loadLedger() {
    try {
      const data = await api.get("/fund/ledger");
      this.ledger.render(data.transactions);
    } catch (err) {
      this.ledger.showError(err.message);
    }
  }

  async submitTransaction(event) {
    event.preventDefault();

    const type = Dom.byId("fund-type").value;
    const amountInput = Dom.byId("fund-amount");
    const noteInput = Dom.byId("fund-note");
    const message = Dom.byId("fund-form-message");
    const button = event.target.querySelector("button[type='submit']");

    amountInput.removeAttribute("aria-invalid");
    const amount = parseInt(amountInput.value, 10);
    if (!amount || amount <= 0) {
      amountInput.setAttribute("aria-invalid", "true");
      Dom.setText("fund-amount-error", "Vui lòng nhập số tiền lớn hơn 0");
      amountInput.focus();
      return;
    }
    Dom.setText("fund-amount-error", "");

    // Thao tác tiền bắt buộc phải xác nhận trước khi ghi
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
      await Promise.all([this.loadBalance(), this.loadLedger()]);
    } catch (err) {
      message.className = "message-error";
      message.textContent = err.message;
      toasts.error(`${type === "topup" ? "Nạp" : "Rút"} quỹ thất bại`, err.message);
    } finally {
      Dom.setBusy(button, false);
    }
  }
}
