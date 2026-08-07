import { ApiClient } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";
import { NutritionWarnings } from "../core/nutritionWarnings.js";

const MAX_QUANTITY = 20;

/** Lưới món ăn kèm bộ đếm số lượng. */
export class MenuGrid {
  constructor(containerId, onChange) {
    this.container = Dom.byId(containerId);
    this.onChange = onChange || (() => {});
    this.items = [];
    this.locked = false;
  }

  showLoading() {
    if (!this.container) return;
    this.container.setAttribute("aria-busy", "true");
    this.container.innerHTML =
      '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>';
  }

  showError(message) {
    if (!this.container) return;
    this.container.setAttribute("aria-busy", "false");
    Dom.clear(this.container).appendChild(Dom.emptyState("⚠️", message));
  }

  render(items, { locked = false } = {}) {
    if (!this.container) return;
    this.items = items || [];
    this.locked = locked;

    this.container.setAttribute("aria-busy", "false");
    Dom.clear(this.container);

    if (!this.items.length) {
      this.container.appendChild(
        Dom.emptyState("🍽️", "Hôm nay chưa có thực đơn. Quản trị viên sẽ cập nhật sớm.")
      );
      return;
    }

    const fragment = document.createDocumentFragment();
    this.items.forEach((item) => fragment.appendChild(this.buildCard(item)));
    this.container.appendChild(fragment);
    this.refreshTotals();
  }

  buildCard(item) {
    const card = Dom.el("article", { class: "menu-item", "data-id": item.id });

    card.appendChild(
      item.image_url
        ? Dom.el("img", {
            class: "thumb",
            src: ApiClient.assetUrl(item.image_url),
            alt: `Ảnh món ${item.name}`,
            loading: "lazy",
            width: 320,
            height: 200,
          })
        : Dom.el("div", {
            class: "thumb-placeholder",
            "aria-hidden": "true",
            text: "Chưa có ảnh",
          })
    );

    card.append(
      Dom.el("h3", { id: `item-${item.id}-name`, text: item.name }),
      Dom.el("div", { class: "price", text: Formatter.money(item.price) })
    );

    if (item.description) card.appendChild(Dom.el("p", { text: item.description }));

    const warnings = NutritionWarnings.detect(item);
    if (warnings.length) {
      card.appendChild(
        Dom.el(
          "div",
          { class: "nutrition-badges" },
          ...warnings.map((w) => Dom.el("span", { class: `nutrition-badge is-${w.type}`, text: w.label }))
        )
      );
    }

    if (item.restaurant_name) {
      const line = Dom.el("div", { class: "restaurant-line", text: item.restaurant_name });
      if (item.restaurant_rating) {
        line.appendChild(
          Dom.el("span", {
            text: ` · ${Number(item.restaurant_rating).toFixed(1)}/5 trên Grab`,
          })
        );
      }
      card.appendChild(line);
    }

    card.appendChild(this.buildQuantityControl(item));
    return card;
  }

  /** Bỏ dấu tiếng Việt để tìm không cần gõ đúng dấu, ví dụ "com" khớp "cơm". */
  static normalize(text) {
    return (text || "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .replace(/đ/gi, "d")
      .toLowerCase();
  }

  /** Ẩn/hiện món theo từ khoá tên/mô tả/thẻ — không mất số lượng đã chọn (Phase 4). */
  filter(query) {
    if (!this.container) return;
    const needle = MenuGrid.normalize(query.trim());

    this.container.querySelectorAll(".menu-item").forEach((card) => {
      const item = this.items.find((m) => m.id === parseInt(card.dataset.id, 10));
      if (!item) return;
      const haystack = MenuGrid.normalize(
        [item.name, item.description, item.tags].filter(Boolean).join(" ")
      );
      card.hidden = Boolean(needle) && !haystack.includes(needle);
    });
  }

  buildQuantityControl(item) {
    const minus = Dom.el("button", {
      type: "button",
      text: "−",
      "aria-label": `Bớt một phần ${item.name}`,
      disabled: true,
    });
    const plus = Dom.el("button", {
      type: "button",
      text: "+",
      "aria-label": `Thêm một phần ${item.name}`,
    });
    const input = Dom.el("input", {
      type: "number",
      id: `qty-${item.id}`,
      class: "quantity-input",
      min: "0",
      max: String(MAX_QUANTITY),
      value: "0",
      inputmode: "numeric",
      "data-id": item.id,
      "aria-describedby": `item-${item.id}-name`,
    });

    // Ghi chú riêng cho món này (mã 3.5) — chỉ bật khi đã chọn ít nhất 1 phần,
    // để tránh gửi ghi chú "mồ côi" cho món không nằm trong đơn.
    const note = Dom.el("input", {
      type: "text",
      class: "note-input",
      "data-note-for": item.id,
      placeholder: "Ghi chú: ít cay, không hành…",
      "aria-label": `Ghi chú cho ${item.name}`,
      maxlength: "200",
      disabled: true,
    });

    const apply = (value) => {
      const next = Math.min(MAX_QUANTITY, Math.max(0, value));
      input.value = String(next);
      minus.disabled = next === 0 || this.locked;
      note.disabled = next === 0 || this.locked;
      if (next === 0) note.value = "";
      this.refreshTotals();
    };

    minus.addEventListener("click", () => apply((parseInt(input.value, 10) || 0) - 1));
    plus.addEventListener("click", () => apply((parseInt(input.value, 10) || 0) + 1));
    input.addEventListener("input", () => apply(parseInt(input.value, 10) || 0));
    note.addEventListener("input", () => this.onChange(this.getSelection()));

    if (this.locked) [minus, plus, input, note].forEach((el) => { el.disabled = true; });

    return Dom.el(
      "div",
      { class: "qty-block" },
      Dom.el(
        "div",
        { class: "qty" },
        Dom.el("label", { for: `qty-${item.id}`, text: "Số lượng" }),
        Dom.el("div", { class: "qty-control" }, minus, input, plus)
      ),
      note
    );
  }

  /** Các món đang được chọn, kèm giá và ghi chú để tính tổng / gửi lên server. */
  getSelection() {
    const selected = [];
    this.container.querySelectorAll(".quantity-input").forEach((input) => {
      const quantity = parseInt(input.value, 10) || 0;
      if (quantity > 0) {
        const item = this.items.find((m) => m.id === parseInt(input.dataset.id, 10));
        if (item) {
          const noteInput = this.container.querySelector(`[data-note-for="${item.id}"]`);
          selected.push({
            menu_item_id: item.id,
            name: item.name,
            price: item.price,
            quantity,
            note: noteInput ? noteInput.value.trim() : "",
          });
        }
      }
    });
    return selected;
  }

  refreshTotals() {
    this.container.querySelectorAll(".menu-item").forEach((card) => {
      const input = card.querySelector(".quantity-input");
      card.classList.toggle("is-selected", (parseInt(input.value, 10) || 0) > 0);
    });
    this.onChange(this.getSelection());
  }

  focusFirstInput() {
    const first = this.container.querySelector(".quantity-input");
    if (first) first.focus();
  }
}
