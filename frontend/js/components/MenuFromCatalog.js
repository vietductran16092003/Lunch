import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";
import { toasts } from "../core/ToastManager.js";

/** Bước 2 "Thực đơn hôm nay": chọn 1 nhà hàng rồi tick món có sẵn trong danh
 * mục của quán đó — không gõ lại tên/giá, và không trộn 2 quán trong 1 ngày. */
export class MenuFromCatalog {
  constructor({ onApplied, getCanEdit, getOwnerName } = {}) {
    this.form = Dom.byId("catalog-apply-form");
    if (!this.form) return;

    this.select = Dom.byId("apply-restaurant");
    this.dateInput = Dom.byId("apply-date");
    this.checklistBox = Dom.byId("catalog-checklist");
    this.submitBtn = Dom.byId("catalog-apply-btn");
    this.onApplied = onApplied || (() => {});
    // admin hoặc đang phụ trách đúng ngày áp dụng thì mới tick/áp dụng được —
    // do AdminPage tính sẵn (đã có status từ round-status), không tự fetch
    // riêng nữa để tránh hở khoá lúc trang mới tải chưa kịp gọi API.
    this.getCanEdit = getCanEdit || (() => true);
    this.getOwnerName = getOwnerName || (() => null);
    this.catalogItems = [];
    this.appliedNames = new Set();
    this.selectedIds = new Set();

    if (!this.dateInput.value) this.dateInput.value = Formatter.todayIso();

    this.select.addEventListener("change", () => this.loadCatalog());
    this.dateInput.addEventListener("change", () => this.loadCatalog());
    this.form.addEventListener("submit", (e) => this.submit(e));
    this.renderChecklist();
  }

  /** AdminPage gọi lại mỗi khi đổi "Ngày áp dụng" hoặc vừa tải xong trang —
   * khoá select/checklist ngay, không cần đợi người dùng tương tác trước. */
  applyLock() {
    this.renderChecklist();
  }

  /** Tải danh mục món của quán đang chọn + tên món đã áp dụng cho ngày đang chọn (để tô "Đã có hôm nay"). */
  async loadCatalog() {
    const restaurantId = this.select.value;
    this.selectedIds = new Set();

    if (!restaurantId) {
      this.catalogItems = [];
      this.appliedNames = new Set();
      this.renderChecklist();
      return;
    }

    try {
      const [catalogData, menuData] = await Promise.all([
        api.get(`/admin/restaurants/${restaurantId}/catalog`),
        this.dateInput.value
          ? api.get(`/menu?date=${encodeURIComponent(this.dateInput.value)}`)
          : Promise.resolve({ items: [] }),
      ]);
      this.catalogItems = catalogData.items || [];
      this.appliedNames = new Set(
        (menuData.items || []).map((i) => (i.name || "").trim().toLowerCase())
      );
      this.renderChecklist();
    } catch (err) {
      toasts.error("Không tải được danh mục món", err.message);
    }
  }

  /** Vẽ lại checklist theo canEdit hiện tại — khoá select+submit và hiện cảnh báo nếu không sửa được. */
  renderChecklist() {
    Dom.clear(this.checklistBox);
    const canEdit = this.getCanEdit();
    this.select.disabled = !canEdit;

    if (!canEdit) {
      const ownerName = this.getOwnerName();
      this.checklistBox.appendChild(
        Dom.notice(
          "warning", null,
          `${ownerName || "Người khác"} đang phụ trách ngày ${this.dateInput.value} — bạn chỉ xem được, chọn ngày khác để tự đặt.`
        )
      );
      this.submitBtn.disabled = true;
      return;
    }

    if (!this.select.value) {
      this.submitBtn.disabled = true;
      return;
    }

    if (!this.catalogItems.length) {
      this.checklistBox.appendChild(
        Dom.emptyState("🍽️", "Quán này chưa có món trong danh mục — thêm ở mục 1 (nút \"Món\").")
      );
      this.submitBtn.disabled = true;
      return;
    }

    const list = Dom.el("div", { class: "catalog-checklist" });
    this.catalogItems.forEach((item) => list.appendChild(this.buildCheckItem(item)));
    this.checklistBox.appendChild(list);
    this.updateSubmitState();
  }

  /** 1 dòng checkbox trong checklist — khoá sẵn nếu món đã có trong thực đơn ngày này rồi. */
  buildCheckItem(item) {
    const already = this.appliedNames.has((item.name || "").trim().toLowerCase());

    const checkbox = Dom.el("input", {
      type: "checkbox",
      id: `catalog-check-${item.id}`,
      disabled: already,
    });
    checkbox.checked = already;
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) this.selectedIds.add(item.id);
      else this.selectedIds.delete(item.id);
      this.updateSubmitState();
    });

    return Dom.el(
      "label",
      { class: "catalog-check-item", for: `catalog-check-${item.id}` },
      checkbox,
      Dom.el("span", { class: "catalog-check-name", text: item.name }),
      Dom.el("span", { class: "catalog-check-price", text: Formatter.money(item.price) }),
      already ? Dom.el("span", { class: "badge closed", text: "Đã có hôm nay" }) : null
    );
  }

  updateSubmitState() {
    this.submitBtn.disabled = this.selectedIds.size === 0;
  }

  /** Áp dụng các món đã tick vào thực đơn ngày đang chọn (copy dữ liệu, không tham chiếu danh mục gốc). */
  async submit(event) {
    event.preventDefault();
    const message = Dom.byId("catalog-apply-message");

    Dom.setBusy(this.submitBtn, true, "Đang áp dụng");
    try {
      const result = await api.post("/admin/menu/from-catalog", {
        available_date: this.dateInput.value,
        restaurant_id: parseInt(this.select.value, 10),
        catalog_ids: [...this.selectedIds],
      });

      message.className = "message-success";
      message.textContent = `Đã thêm ${result.created} món vào thực đơn.`;
      toasts.success("Đã áp dụng vào thực đơn", `${result.created} món`);

      await this.loadCatalog();
      await this.onApplied();
    } catch (err) {
      message.className = "message-error";
      message.textContent = err.message;
      toasts.error("Áp dụng thất bại", err.message);
    } finally {
      Dom.setBusy(this.submitBtn, false);
    }
  }
}
