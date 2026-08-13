import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";
import { toasts } from "../core/ToastManager.js";

/** Danh sách món đã thêm cho một ngày, kèm sửa/xóa (mã 2. Thực đơn hôm nay). */
export class MenuItemsList {
  constructor({ getRestaurants, getUser }) {
    this.container = Dom.byId("menu-items-list");
    this.editorBox = Dom.byId("menu-items-editor");
    this.getRestaurants = getRestaurants || (() => []);
    this.getUser = getUser || (() => null);
    this.items = [];
    this.date = null;
    // Chỉ admin hoặc người đang phụ trách đúng ngày này mới sửa/xoá được
    this.canEdit = true;
  }

  /** Tải món của một ngày + tự tính canEdit (admin hoặc đúng chủ ngày đó) từ round-status. */
  async load(date) {
    if (!this.container) return;
    this.date = date;
    this.container.setAttribute("aria-busy", "true");

    try {
      const [data, status] = await Promise.all([
        api.get(`/menu?date=${encodeURIComponent(date)}`),
        api.get(`/orders/round-status?date=${encodeURIComponent(date)}`).catch(() => null),
      ]);
      this.items = data.items || [];
      const user = this.getUser();
      this.canEdit = !status || !status.owner || !user
        || user.is_admin || status.owner.id === user.id;
      this.render();
    } catch (err) {
      Dom.clear(this.container).appendChild(Dom.emptyState("⚠️", "Không tải được danh sách món."));
    } finally {
      this.container.setAttribute("aria-busy", "false");
    }
  }

  render() {
    if (!this.container) return;
    Dom.clear(this.container);

    if (!this.items.length) {
      this.container.appendChild(
        Dom.emptyState("🍽️", "Chưa có món nào cho ngày này. Tick món ở form bên trên.")
      );
      return;
    }

    const grid = Dom.el("div", { class: "menu-items-simple" });
    this.items.forEach((item) => grid.appendChild(this.buildCard(item)));
    this.container.appendChild(grid);
  }

  /** 1 thẻ món — nút Sửa/Xóa chỉ hiện nếu canEdit. */
  buildCard(item) {
    const card = Dom.el("article", { class: "menu-item-row", "data-id": item.id });

    card.append(
      Dom.el(
        "div",
        { class: "menu-item-row-info" },
        Dom.el("h3", { text: item.name }),
        Dom.el("div", { class: "price", text: Formatter.money(item.price) }),
        item.description ? Dom.el("p", { text: item.description }) : null
      )
    );

    if (this.canEdit) {
      const edit = Dom.el("button", {
        type: "button",
        class: "ghost",
        text: "Sửa",
        "aria-label": `Sửa món ${item.name}`,
      });
      edit.addEventListener("click", () => this.openEditor(item));

      const remove = Dom.el("button", {
        type: "button",
        class: "danger",
        text: "Xóa",
        "aria-label": `Xóa món ${item.name}`,
      });
      remove.addEventListener("click", () => this.delete(item, remove));

      card.appendChild(Dom.el("div", { class: "menu-item-row-actions" }, edit, remove));
    }

    return card;
  }

  /** Form sửa 1 món tại chỗ, hiện dưới danh sách (menu-items-editor). */
  openEditor(item) {
    if (!this.editorBox) return;
    Dom.clear(this.editorBox);

    const field = (id, labelText, value, type = "text", extra = {}) => {
      const input = Dom.el("input", { type, id, value: value == null ? "" : value, ...extra });
      return {
        input,
        node: Dom.el("div", { class: "field field-sm" }, Dom.el("label", { for: id, text: labelText }), input),
      };
    };

    const name = field("edit-item-name", "Tên món", item.name);
    const price = field("edit-item-price", "Giá (đ)", item.price, "number", { min: "0", step: "1000" });
    const date = field("edit-item-date", "Ngày áp dụng", item.available_date, "date");
    const description = field("edit-item-description", "Mô tả", item.description);
    const tags = field("edit-item-tags", "Thẻ (phân cách bằng dấu phẩy)", item.tags);

    const restaurantSelect = Dom.el("select", { id: "edit-item-restaurant" });
    this.getRestaurants().forEach((r) => {
      restaurantSelect.appendChild(Dom.el("option", { value: r.id, text: r.name }));
    });
    restaurantSelect.value = item.restaurant_id;
    const restaurantField = Dom.el(
      "div",
      { class: "field field-sm" },
      Dom.el("label", { for: "edit-item-restaurant", text: "Nhà hàng" }),
      restaurantSelect
    );

    const save = Dom.el("button", { type: "submit", text: "Lưu thay đổi" });
    const cancel = Dom.el("button", { type: "button", class: "ghost", text: "Hủy" });
    cancel.addEventListener("click", () => Dom.clear(this.editorBox));

    const message = Dom.el("p", { role: "status", "aria-live": "polite", style: "margin:0;" });

    const form = Dom.el(
      "form",
      { style: "background:none; border:none; padding:0;" },
      Dom.el(
        "div",
        { style: "display:flex; flex-wrap:wrap; gap:12px;" },
        restaurantField, name.node, price.node, date.node, description.node, tags.node
      ),
      Dom.el("div", { style: "display:flex; gap:8px; margin-top:12px;" }, save, cancel),
      message
    );

    this.editorBox.appendChild(
      Dom.el("div", { class: "card" }, Dom.el("h3", { text: `Sửa: ${item.name}` }), form)
    );

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!name.input.value.trim() || !price.input.value) {
        message.className = "message-error";
        message.textContent = "Vui lòng nhập đủ tên món và giá";
        return;
      }

      Dom.setBusy(save, true, "Đang lưu");
      try {
        await api.put(`/admin/menu/${item.id}`, {
          name: name.input.value.trim(),
          description: description.input.value.trim(),
          price: parseFloat(price.input.value),
          available_date: date.input.value,
          restaurant_id: parseInt(restaurantSelect.value, 10),
          tags: tags.input.value.trim(),
        });
        toasts.success("Đã lưu món", name.input.value.trim());
        Dom.clear(this.editorBox);
        await this.load(this.date);
      } catch (err) {
        Dom.setBusy(save, false);
        message.className = "message-error";
        message.textContent = err.message;
        toasts.error("Lưu thất bại", err.message);
      }
    });

    name.input.focus();
  }

  async delete(item, button) {
    if (!window.confirm(`Xóa món "${item.name}"?`)) return;
    Dom.setBusy(button, true, "Đang xóa");
    try {
      await api.delete(`/admin/menu/${item.id}`);
      toasts.info("Đã xóa món", item.name);
      await this.load(this.date);
    } catch (err) {
      Dom.setBusy(button, false);
      toasts.error("Không xóa được", err.message);
    }
  }
}
