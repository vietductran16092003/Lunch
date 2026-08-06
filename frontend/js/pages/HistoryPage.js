import { HistoryList } from "../components/HistoryList.js";
import { api } from "../core/ApiClient.js";
import { BasePage } from "./BasePage.js";

/** Trang lịch sử đặt món. */
export class HistoryPage extends BasePage {
  constructor() {
    super();
    this.list = new HistoryList();
  }

  async init() {
    await this.load();
    // Người đặt xác nhận nhận tiền thì lịch sử phải đổi trạng thái ngay
    this.listen({ payment_confirmed: () => this.load() });
  }

  async load() {
    try {
      const data = await api.get("/orders/history");
      this.list.render(data.history);
    } catch (err) {
      this.list.showError("Không tải được lịch sử.");
    }
  }
}
