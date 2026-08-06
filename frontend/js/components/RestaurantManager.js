import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { toasts } from "../core/ToastManager.js";

/** Thêm nhà hàng từ đường dẫn GrabFood và quản lý danh sách đã lưu. */
export class RestaurantManager {
  constructor({ onChange } = {}) {
    this.form = Dom.byId("restaurant-form");
    this.urlInput = Dom.byId("grab-url");
    this.fetchBtn = Dom.byId("grab-fetch-btn");
    this.previewBox = Dom.byId("restaurant-preview");
    this.listBox = Dom.byId("restaurant-list");
    this.select = Dom.byId("item-restaurant");
    this.onChange = onChange || (() => {});
    this.restaurants = [];

    if (this.form) this.bind();
  }

  bind() {
    this.fetchBtn.addEventListener("click", () => this.preview());
    this.form.addEventListener("submit", (e) => {
      e.preventDefault();
      this.preview();
    });
  }

  async load() {
    try {
      const data = await api.get("/restaurants");
      this.restaurants = data.restaurants || [];
    } catch (err) {
      this.restaurants = [];
    }
    this.renderSelect();
    this.renderList();
    this.onChange(this.restaurants);
    return this.restaurants;
  }

  renderSelect() {
    if (!this.select) return;
    const previous = this.select.value;
    Dom.clear(this.select);
    this.select.appendChild(Dom.el("option", { value: "", text: "— Chọn nhà hàng —" }));

    this.restaurants.forEach((r) => {
      this.select.appendChild(
        Dom.el("option", {
          value: r.id,
          text: r.rating ? `${r.name} (${Number(r.rating).toFixed(1)}★)` : r.name,
        })
      );
    });

    if (previous) this.select.value = previous;
  }

  renderList() {
    if (!this.listBox) return;
    Dom.clear(this.listBox);

    if (!this.restaurants.length) {
      this.listBox.appendChild(
        Dom.emptyState("🏪", "Chưa có nhà hàng nào. Dán đường dẫn GrabFood ở trên để thêm.")
      );
      return;
    }

    const tbody = Dom.el("tbody");
    this.restaurants.forEach((r) => tbody.appendChild(this.buildRow(r)));

    const table = Dom.el("table", {
      html:
        "<caption>Nhà hàng đã lưu</caption>" +
        "<thead><tr><th scope='col'>Tên quán</th><th scope='col'>Đánh giá</th>" +
        "<th scope='col'>Địa chỉ</th><th scope='col'>Grab</th>" +
        "<th scope='col'>Thao tác</th></tr></thead>",
    });
    table.appendChild(tbody);
    this.listBox.appendChild(Dom.el("div", { class: "table-wrap" }, table));
  }

  buildRow(restaurant) {
    const remove = Dom.el("button", {
      type: "button",
      class: "danger",
      text: "Xóa",
      "aria-label": `Xóa nhà hàng ${restaurant.name}`,
    });
    remove.addEventListener("click", () => this.delete(restaurant, remove));

    return Dom.el(
      "tr",
      {},
      Dom.el("td", { text: restaurant.name }),
      Dom.el("td", {
        class: "num",
        text: restaurant.rating ? `${Number(restaurant.rating).toFixed(1)} / 5` : "—",
      }),
      Dom.el("td", { text: restaurant.address || "—" }),
      Dom.el(
        "td",
        {},
        restaurant.grab_url
          ? Dom.el("a", {
              href: restaurant.grab_url,
              target: "_blank",
              rel: "noopener noreferrer",
              class: "link-action",
              text: "Mở Grab",
              "aria-label": `Mở trang GrabFood của ${restaurant.name} trong tab mới`,
            })
          : "—"
      ),
      Dom.el("td", {}, remove)
    );
  }

  async delete(restaurant, button) {
    if (!window.confirm(`Xóa nhà hàng "${restaurant.name}"?`)) return;
    Dom.setBusy(button, true, "Đang xóa");
    try {
      await api.delete(`/admin/restaurants/${restaurant.id}`);
      toasts.info("Đã xóa nhà hàng");
      await this.load();
    } catch (err) {
      Dom.setBusy(button, false);
      toasts.error("Không xóa được", err.message);
    }
  }

  async preview() {
    this.urlInput.removeAttribute("aria-invalid");

    if (!this.urlInput.value.trim()) {
      this.urlInput.setAttribute("aria-invalid", "true");
      this.urlInput.focus();
      toasts.warning("Chưa có đường dẫn", "Dán đường dẫn nhà hàng trên GrabFood vào ô này.");
      return;
    }

    Dom.setBusy(this.fetchBtn, true, "Đang lấy thông tin nhà hàng");
    try {
      const data = await api.post("/admin/restaurants/preview", {
        grab_url: this.urlInput.value.trim(),
      });
      this.renderPreview(data.restaurant, data.hint);
    } catch (err) {
      this.urlInput.setAttribute("aria-invalid", "true");
      toasts.error("Không đọc được đường dẫn", err.message);
    } finally {
      Dom.setBusy(this.fetchBtn, false);
    }
  }

  renderPreview(info, hint) {
    if (!this.previewBox) return;
    Dom.clear(this.previewBox);

    const field = (id, labelText, value, type = "text") => {
      const input = Dom.el("input", { type, id, value: value || "" });
      if (type === "number") {
        Object.assign(input, { min: "0", max: "5", step: "0.1" });
      }
      return {
        input,
        node: Dom.el(
          "div",
          { class: "field" },
          Dom.el("label", { for: id, text: labelText }),
          input
        ),
      };
    };

    const name = field("preview-name", "Tên nhà hàng", info.name);
    const address = field("preview-address", "Địa chỉ", info.address);
    const rating = field("preview-rating", "Đánh giá (0–5)", info.rating, "number");

    const save = Dom.el("button", {
      type: "button",
      text: "Lưu nhà hàng",
      style: "margin-top:12px;",
    });
    save.addEventListener("click", () => this.save(info, { name, address, rating }, save));

    const card = Dom.el(
      "div",
      { class: "card" },
      Dom.el("h3", { text: "Kiểm tra thông tin trước khi lưu" }),
      hint ? Dom.notice("info", null, hint) : null,
      Dom.el(
        "div",
        { style: "display:flex; flex-wrap:wrap; gap:12px;" },
        name.node,
        address.node,
        rating.node
      ),
      save
    );

    this.previewBox.appendChild(card);
    name.input.focus();
  }

  async save(info, fields, button) {
    if (!fields.name.input.value.trim()) {
      fields.name.input.setAttribute("aria-invalid", "true");
      fields.name.input.focus();
      toasts.warning("Thiếu tên nhà hàng");
      return;
    }

    Dom.setBusy(button, true, "Đang lưu nhà hàng");
    try {
      await api.post("/admin/restaurants", {
        name: fields.name.input.value.trim(),
        address: fields.address.input.value.trim(),
        rating: fields.rating.input.value,
        grab_url: info.grab_url,
        external_id: info.external_id,
      });
      toasts.success("Đã lưu nhà hàng", fields.name.input.value.trim());
      Dom.clear(this.previewBox);
      this.urlInput.value = "";
      await this.load();
    } catch (err) {
      Dom.setBusy(button, false);
      toasts.error("Lưu thất bại", err.message);
    }
  }
}
