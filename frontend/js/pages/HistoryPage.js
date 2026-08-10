import { HistoryList } from "../components/HistoryList.js";
import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { toasts } from "../core/ToastManager.js";
import { BasePage } from "./BasePage.js";

/** Trang lịch sử đặt món. */
export class HistoryPage extends BasePage {
  constructor() {
    super();
    this.history = [];
    this.list = new HistoryList("history-list", {
      onReorder: (order, button) => this.reorder(order, button),
      onSelectionChange: (selected) => this.updateToolbar(selected),
    });
  }

  async init() {
    Dom.byId("history-select-all").addEventListener("change", (e) => this.toggleSelectAll(e));
    Dom.byId("history-delete-selected").addEventListener("click", () => this.deleteSelected());

    await this.load();
    // Người đặt xác nhận nhận tiền thì lịch sử phải đổi trạng thái ngay
    this.listen({ payment_confirmed: () => this.load() });
  }

  async load() {
    try {
      const [history, menu] = await Promise.all([
        api.get("/orders/history"),
        api.get("/menu"),
      ]);
      this.history = history.history || [];
      const todayKeys = new Set(
        (menu.items || []).map((item) => HistoryList.itemKey(item.name, item.restaurant_name))
      );
      this.list.render(this.history, todayKeys);

      const toolbar = Dom.byId("history-toolbar");
      const hasPending = this.list.pendingIds(this.history).length > 0;
      toolbar.hidden = !hasPending;
      Dom.byId("history-select-all").checked = false;
      this.updateToolbar(new Set());
    } catch (err) {
      this.list.showError("Không tải được lịch sử.");
    }
  }

  updateToolbar(selected) {
    const button = Dom.byId("history-delete-selected");
    button.disabled = selected.size === 0;
    button.textContent = selected.size ? `Xoá đã chọn (${selected.size})` : "Xoá đã chọn";
  }

  toggleSelectAll(event) {
    const ids = event.target.checked ? this.list.pendingIds(this.history) : [];
    this.list.setSelected(ids);
  }

  async deleteSelected() {
    const ids = [...this.list.selected];
    if (!ids.length) return;
    if (!window.confirm(`Xoá ${ids.length} đơn đang chờ đã chọn? Không thể hoàn tác.`)) return;

    const button = Dom.byId("history-delete-selected");
    Dom.setBusy(button, true, "Đang xoá");
    try {
      await Promise.all(ids.map((id) => api.delete(`/orders/${id}`)));
      toasts.success("Đã xoá đơn", `${ids.length} đơn đang chờ`);
      await this.load();
    } catch (err) {
      toasts.error("Xoá không thành công", err.message);
      await this.load();
    } finally {
      Dom.setBusy(button, false);
    }
  }

  /** Đặt lại nhanh từ một đơn cũ cho hôm nay (mã 3.3). */
  async reorder(order, button) {
    if (!window.confirm(
      `Đặt lại các món trong đơn ngày ${order.order_date} cho hôm nay? ` +
        "Đơn hôm nay hiện có (nếu chưa chốt) sẽ bị ghi đè."
    )) {
      return;
    }

    Dom.setBusy(button, true, "Đang đặt lại đơn");
    try {
      const result = await api.post(`/orders/reorder/${order.id}`, {});
      const skipped = result.skipped_items || [];

      toasts.success(
        "Đã đặt lại đơn cho hôm nay",
        skipped.length
          ? `Hết bán nên bỏ qua: ${skipped.join(", ")}. Vào trang Thực đơn để xem lại.`
          : "Vào trang Thực đơn để xem lại."
      );
    } catch (err) {
      toasts.error("Không đặt lại được đơn", err.message);
    } finally {
      Dom.setBusy(button, false);
    }
  }
}
