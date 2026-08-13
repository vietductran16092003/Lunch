import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";
import { NutritionWarnings } from "../core/nutritionWarnings.js";

const MAX_QUANTITY = 20;
const PAGE_SIZE = 12;

/** Lưới món ăn kèm bộ đếm số lượng và phân trang.
 *
 * Số lượng/ghi chú đã chọn được lưu trong `this.selections` (tách khỏi DOM),
 * vì phân trang chỉ render một phần món tại một thời điểm — nếu đọc số lượng
 * thẳng từ input trên trang thì sẽ mất lựa chọn của các món ở trang khác.
 */
export class MenuGrid {
  constructor(containerId, onChange) {
    this.container = Dom.byId(containerId);
    this.onChange = onChange || (() => {});
    this.items = [];
    this.locked = false;
    this.selections = new Map(); // id -> { quantity, note }
    this.query = "";
    this.page = 1;
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
    this.selections = new Map();
    this.query = "";
    this.page = 1;
    this.renderPage();
  }

  /** Bỏ dấu tiếng Việt để tìm không cần gõ đúng dấu, ví dụ "com" khớp "cơm". */
  static normalize(text) {
    return (text || "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .replace(/đ/gi, "d")
      .toLowerCase();
  }

  /** Ẩn/hiện món theo đúng TÊN món — không lọc theo mô tả/thẻ nữa, để kết quả
   * chỉ còn món trùng tên như yêu cầu. Không mất số lượng đã chọn (Phase 4). */
  filter(query) {
    this.query = (query || "").trim();
    this.page = 1;
    this.renderPage();
  }

  getFilteredItems() {
    if (!this.query) return this.items;
    const needle = MenuGrid.normalize(this.query);
    return this.items.filter((item) => MenuGrid.normalize(item.name || "").includes(needle));
  }

  renderPage() {
    if (!this.container) return;
    this.container.setAttribute("aria-busy", "false");
    Dom.clear(this.container);
    if (this.pager) this.pager.remove();

    if (!this.items.length) {
      this.container.appendChild(
        Dom.emptyState("🍽️", "Hôm nay chưa có thực đơn. Quản trị viên sẽ cập nhật sớm.")
      );
      return;
    }

    const filtered = this.getFilteredItems();
    if (!filtered.length) {
      this.container.appendChild(Dom.emptyState("🔎", "Không tìm thấy món phù hợp."));
      return;
    }

    const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
    this.page = Math.min(Math.max(1, this.page), totalPages);
    const start = (this.page - 1) * PAGE_SIZE;
    const pageItems = filtered.slice(start, start + PAGE_SIZE);

    const fragment = document.createDocumentFragment();
    pageItems.forEach((item) => fragment.appendChild(this.buildCard(item)));
    this.container.appendChild(fragment);

    this.pager = this.buildPager(totalPages, filtered.length);
    this.container.insertAdjacentElement("afterend", this.pager);

    this.refreshTotals();
  }

  buildPager(totalPages, totalCount) {
    if (totalPages <= 1) return Dom.el("div", { hidden: true });

    const prev = Dom.el("button", { type: "button", class: "ghost", text: "‹ Trước" });
    prev.disabled = this.page <= 1;
    prev.addEventListener("click", () => this.goToPage(this.page - 1));

    const next = Dom.el("button", { type: "button", class: "ghost", text: "Sau ›" });
    next.disabled = this.page >= totalPages;
    next.addEventListener("click", () => this.goToPage(this.page + 1));

    const status = Dom.el("span", {
      class: "subtitle",
      style: "margin:0;",
      text: `Trang ${this.page}/${totalPages} · ${totalCount} món`,
    });

    return Dom.el("nav", { class: "pagination", "aria-label": "Phân trang danh sách món" }, prev, status, next);
  }

  goToPage(page) {
    this.page = page;
    this.renderPage();
    this.container.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  buildCard(item) {
    const card = Dom.el("article", { class: "menu-item", "data-id": item.id });

    card.append(
      Dom.el("h3", { id: `item-${item.id}-name` }, Dom.el("span", { "aria-hidden": "true", text: "🍴 " }), document.createTextNode(item.name)),
      Dom.el("div", { class: "price" }, Dom.el("span", { "aria-hidden": "true", text: "💵 " }), document.createTextNode(Formatter.money(item.price)))
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

  buildQuantityControl(item) {
    const saved = this.selections.get(item.id);
    const savedQuantity = saved ? saved.quantity : 0;

    const minus = Dom.el("button", {
      type: "button",
      text: "−",
      "aria-label": `Bớt một phần ${item.name}`,
      disabled: savedQuantity === 0,
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
      value: String(savedQuantity),
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
      value: saved ? saved.note || "" : "",
      disabled: savedQuantity === 0,
    });

    const apply = (value) => {
      const next = Math.min(MAX_QUANTITY, Math.max(0, value));
      input.value = String(next);
      minus.disabled = next === 0 || this.locked;
      note.disabled = next === 0 || this.locked;
      if (next === 0) note.value = "";
      this.setSelection(item, next, note.value);
      this.refreshTotals();
    };

    minus.addEventListener("click", () => apply((parseInt(input.value, 10) || 0) - 1));
    plus.addEventListener("click", () => apply((parseInt(input.value, 10) || 0) + 1));
    input.addEventListener("input", () => apply(parseInt(input.value, 10) || 0));
    note.addEventListener("input", () => {
      this.setSelection(item, parseInt(input.value, 10) || 0, note.value);
      this.onChange(this.getSelection());
    });

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

  setSelection(item, quantity, note) {
    if (quantity > 0) {
      this.selections.set(item.id, { quantity, note: (note || "").trim() });
    } else {
      this.selections.delete(item.id);
    }
  }

  /** Thêm/bớt số lượng một món theo id, kể cả khi món đó không nằm ở trang
   * đang xem (dùng cho chip gợi ý). Vẽ lại trang chỉ khi món đó đang hiển thị. */
  addQuantity(itemId, delta) {
    const item = this.items.find((m) => m.id === itemId);
    if (!item) return;
    const current = this.selections.get(itemId);
    const next = Math.min(MAX_QUANTITY, Math.max(0, (current ? current.quantity : 0) + delta));
    this.setSelection(item, next, current ? current.note : "");

    const input = this.container.querySelector(`.quantity-input[data-id="${itemId}"]`);
    if (input) {
      input.value = String(next);
      input.dispatchEvent(new Event("input"));
    } else {
      this.onChange(this.getSelection());
    }
  }

  /** Các món đang được chọn, kèm giá và ghi chú để tính tổng / gửi lên server. */
  getSelection() {
    const selected = [];
    this.items.forEach((item) => {
      const saved = this.selections.get(item.id);
      if (saved && saved.quantity > 0) {
        selected.push({
          menu_item_id: item.id,
          name: item.name,
          price: item.price,
          quantity: saved.quantity,
          note: saved.note || "",
        });
      }
    });
    return selected;
  }

  refreshTotals() {
    this.container.querySelectorAll(".menu-item").forEach((card) => {
      const id = parseInt(card.dataset.id, 10);
      const saved = this.selections.get(id);
      card.classList.toggle("is-selected", Boolean(saved && saved.quantity > 0));
    });
    this.onChange(this.getSelection());
  }

  focusFirstInput() {
    const first = this.container.querySelector(".quantity-input");
    if (first) first.focus();
  }
}
