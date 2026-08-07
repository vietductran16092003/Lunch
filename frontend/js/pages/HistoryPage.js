import { HistoryList } from "../components/HistoryList.js";
import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { toasts } from "../core/ToastManager.js";
import { BasePage } from "./BasePage.js";

/** Trang lịch sử đặt món. */
export class HistoryPage extends BasePage {
  constructor() {
    super();
    this.list = new HistoryList("history-list", {
      onReorder: (order, button) => this.reorder(order, button),
    });
  }

  async init() {
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
      const todayKeys = new Set(
        (menu.items || []).map((item) => HistoryList.itemKey(item.name, item.restaurant_name))
      );
      this.list.render(history.history, todayKeys);
    } catch (err) {
      this.list.showError("Không tải được lịch sử.");
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
