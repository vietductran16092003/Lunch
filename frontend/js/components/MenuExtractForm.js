import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { Formatter } from "../core/Formatter.js";
import { toasts } from "../core/ToastManager.js";

/** Dán văn bản menu, xem trước và lưu hàng loạt (Phase 3, mã 7.7). */
export class MenuExtractForm {
  constructor({ onSaved } = {}) {
    this.select = Dom.byId("extract-restaurant");
    this.dateInput = Dom.byId("extract-date");
    this.textInput = Dom.byId("extract-text");
    this.previewBtn = Dom.byId("extract-preview-btn");
    this.message = Dom.byId("extract-message");
    this.previewBox = Dom.byId("extract-preview-box");
    this.onSaved = onSaved || (() => {});

    if (!this.previewBtn) return;
    this.dateInput.value = Formatter.todayIso();
    this.previewBtn.addEventListener("click", () => this.preview());
  }

  updateRestaurants(restaurants) {
    if (!this.select) return;
    const previous = this.select.value;
    Dom.clear(this.select);
    this.select.appendChild(Dom.el("option", { value: "", text: "— Chọn nhà hàng —" }));
    (restaurants || []).forEach((r) => {
      this.select.appendChild(Dom.el("option", { value: r.id, text: r.name }));
    });
    if (previous) this.select.value = previous;
  }

  async preview() {
    this.message.className = "";
    this.message.textContent = "";

    const restaurantId = this.select.value;
    const date = this.dateInput.value;
    const text = this.textInput.value.trim();

    if (!restaurantId) {
      this.message.className = "message-error";
      this.message.textContent = "Vui lòng chọn nhà hàng";
      this.select.focus();
      return;
    }
    if (!date) {
      this.message.className = "message-error";
      this.message.textContent = "Vui lòng chọn ngày áp dụng";
      this.dateInput.focus();
      return;
    }
    if (!text) {
      this.message.className = "message-error";
      this.message.textContent = "Vui lòng dán văn bản menu";
      this.textInput.focus();
      return;
    }

    Dom.setBusy(this.previewBtn, true, "Đang phân tích");
    try {
      const data = await api.post("/ai/extract-menu", {
        text, restaurant_id: Number(restaurantId), available_date: date,
      });
      this.renderPreview(data, Number(restaurantId), date);
    } catch (err) {
      this.message.className = "message-error";
      this.message.textContent = err.message;
    } finally {
      Dom.setBusy(this.previewBtn, false);
    }
  }

  renderPreview(data, restaurantId, date) {
    Dom.clear(this.previewBox);

    if (!data.items.length) {
      this.previewBox.appendChild(
        Dom.emptyState("🤔", "Không nhận diện được món nào. Kiểm tra lại định dạng mỗi dòng.")
      );
      return;
    }

    const tbody = Dom.el("tbody");
    data.items.forEach((item) => {
      tbody.appendChild(
        Dom.el(
          "tr",
          {},
          Dom.el("td", { text: item.name }),
          Dom.el("td", { class: "num mono", text: Formatter.money(item.price) })
        )
      );
    });

    const table = Dom.el("table", {
      html:
        "<caption>Món nhận diện được — kiểm tra trước khi lưu</caption>" +
        "<thead><tr><th scope='col'>Tên món</th><th scope='col' class='num'>Giá</th></tr></thead>",
    });
    table.appendChild(tbody);

    const saveBtn = Dom.el("button", { type: "button", text: `Lưu ${data.items.length} món` });
    saveBtn.addEventListener("click", () => this.save(data.items, restaurantId, date, saveBtn));

    this.previewBox.append(
      Dom.el("div", { class: "table-wrap" }, table),
      data.unparsed_lines.length
        ? Dom.notice(
            "warning",
            `${data.unparsed_lines.length} dòng không đọc được`,
            data.unparsed_lines.join(" · ")
          )
        : null,
      Dom.el("div", { style: "margin-top:8px;" }, saveBtn)
    );
  }

  async save(items, restaurantId, date, button) {
    Dom.setBusy(button, true, "Đang lưu");
    try {
      const result = await api.post("/ai/extract-menu/save", {
        items, restaurant_id: restaurantId, available_date: date,
      });
      toasts.success("Đã lưu thực đơn", `${result.created} món cho ngày ${date}`);
      Dom.clear(this.previewBox);
      this.textInput.value = "";
      this.onSaved();
    } catch (err) {
      Dom.setBusy(button, false);
      toasts.error("Lưu thất bại", err.message);
    }
  }
}
