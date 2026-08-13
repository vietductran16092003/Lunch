import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";
import { toasts } from "../core/ToastManager.js";

/** Danh mục món "gốc" của một nhà hàng — nhập một lần, dùng lại cho nhiều
 * ngày ở bước "Thực đơn hôm nay" (chỉ tick chọn, không phải gõ lại). */
export class CatalogManager {
  constructor(containerId = "catalog-panel", { onChange, getCanEdit } = {}) {
    this.container = Dom.byId(containerId);
    this.onChange = onChange || (() => {});
    this.getCanEdit = getCanEdit || (() => true);
    this.restaurant = null;
    this.items = [];
  }

  /** Mở panel danh mục món của một nhà hàng cụ thể (nút "Món" ở mục 1). */
  async open(restaurant) {
    if (!this.container) return;
    this.restaurant = restaurant;
    await this.load();
    this.container.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  close() {
    this.restaurant = null;
    if (this.container) Dom.clear(this.container);
  }

  async load() {
    if (!this.container || !this.restaurant) return;
    try {
      const data = await api.get(`/admin/restaurants/${this.restaurant.id}/catalog`);
      this.items = data.items || [];
      this.render();
    } catch (err) {
      toasts.error("Không tải được danh mục món", err.message);
    }
  }

  render() {
    if (!this.container) return;
    Dom.clear(this.container);
    if (!this.restaurant) return;

    const closeBtn = Dom.el("button", {
      type: "button", class: "ghost", text: "Đóng",
      "aria-label": "Đóng danh mục món",
    });
    closeBtn.addEventListener("click", () => this.close());

    const head = Dom.el(
      "div",
      { style: "display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:12px;" },
      Dom.el("h3", { style: "margin:0;", text: `Danh mục món — ${this.restaurant.name}` }),
      closeBtn
    );

    const list = this.items.length
      ? Dom.el(
          "div",
          { class: "table-wrap" },
          this.buildTable()
        )
      : Dom.emptyState("🍽️", "Nhà hàng này chưa có món nào trong danh mục — thêm ở form bên dưới.");

    this.container.appendChild(
      Dom.el("div", { class: "card" }, head, list, this.buildAddForm())
    );
  }

  buildTable() {
    const tbody = Dom.el("tbody");
    this.items.forEach((item) => tbody.appendChild(this.buildRow(item)));

    const table = Dom.el("table", {
      html:
        "<thead><tr><th scope='col'>Tên món</th><th scope='col' class='num'>Giá</th>" +
        "<th scope='col'>Thẻ</th><th scope='col'>Thao tác</th></tr></thead>",
    });
    table.appendChild(tbody);
    return table;
  }

  /** 1 dòng trong bảng danh mục — nút Xóa chỉ hiện nếu canEdit (khoá theo ngày áp dụng). */
  buildRow(item) {
    let remove = null;
    if (this.getCanEdit()) {
      remove = Dom.el("button", {
        type: "button", class: "danger", text: "Xóa",
        "aria-label": `Xóa ${item.name} khỏi danh mục`,
      });
      remove.addEventListener("click", () => this.delete(item, remove));
    }

    return Dom.el(
      "tr",
      {},
      Dom.el("td", { text: item.name }),
      Dom.el("td", { class: "num mono", text: Formatter.money(item.price) }),
      Dom.el("td", { text: item.tags || "—" }),
      Dom.el("td", {}, remove || "—")
    );
  }

  /** Form thêm 1 món mới vào danh mục gốc — chưa gán ngày nào, chỉ để tick áp dụng sau. */
  buildAddForm() {
    const name = Dom.el("input", { type: "text", id: "catalog-item-name", autocomplete: "off" });
    const price = Dom.el("input", {
      type: "number", id: "catalog-item-price", min: "0", step: "1000", inputmode: "numeric",
    });
    const tags = Dom.el("input", {
      type: "text", id: "catalog-item-tags", autocomplete: "off", placeholder: "cơm, cay, chay",
    });
    const message = Dom.el("p", { role: "status", "aria-live": "polite", style: "margin:0;" });
    const canEdit = this.getCanEdit();
    const submit = Dom.el("button", { type: "submit", text: "Thêm vào danh mục", disabled: !canEdit });
    name.disabled = !canEdit;
    price.disabled = !canEdit;
    tags.disabled = !canEdit;

    const form = Dom.el(
      "form",
      { style: "background:none; border:none; padding:0; margin-top:12px;" },
      Dom.el(
        "div",
        { style: "display:flex; flex-wrap:wrap; gap:12px;" },
        Dom.el("div", { class: "field" }, Dom.el("label", { for: "catalog-item-name", text: "Tên món" }), name),
        Dom.el("div", { class: "field field-sm" }, Dom.el("label", { for: "catalog-item-price", text: "Giá (đ)" }), price),
        Dom.el("div", { class: "field field-lg" }, Dom.el("label", { for: "catalog-item-tags", text: "Thẻ" }), tags)
      ),
      submit,
      message
    );

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!name.value.trim() || !price.value) {
        message.className = "message-error";
        message.textContent = "Vui lòng nhập tên món và giá";
        return;
      }

      Dom.setBusy(submit, true, "Đang thêm");
      try {
        await api.post(`/admin/restaurants/${this.restaurant.id}/catalog`, {
          name: name.value.trim(),
          price: parseFloat(price.value),
          tags: tags.value.trim(),
        });
        toasts.success("Đã thêm vào danh mục", name.value.trim());
        name.value = "";
        price.value = "";
        tags.value = "";
        await this.load();
        this.onChange();
      } catch (err) {
        message.className = "message-error";
        message.textContent = err.message;
      } finally {
        Dom.setBusy(submit, false);
      }
    });

    return form;
  }

  async delete(item, button) {
    if (!window.confirm(`Xóa "${item.name}" khỏi danh mục? Không ảnh hưởng món đã áp dụng cho các ngày trước đó.`)) {
      return;
    }
    Dom.setBusy(button, true, "Đang xóa");
    try {
      await api.delete(`/admin/catalog/${item.id}`);
      toasts.info("Đã xóa khỏi danh mục", item.name);
      await this.load();
      this.onChange();
    } catch (err) {
      Dom.setBusy(button, false);
      toasts.error("Không xóa được", err.message);
    }
  }
}
