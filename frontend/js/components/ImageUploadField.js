import { ApiClient, api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { toasts } from "../core/ToastManager.js";

/** Ô chọn ảnh: xem trước ngay từ máy rồi tải lên nền. */
export class ImageUploadField {
  constructor({ inputId, previewId, emptyId, label = "ảnh" }) {
    this.input = Dom.byId(inputId);
    this.preview = Dom.byId(previewId);
    this.empty = Dom.byId(emptyId);
    this.label = label;
    this.url = null;

    if (this.input) this.input.addEventListener("change", () => this.handleChange());
  }

  async handleChange() {
    const file = this.input.files && this.input.files[0];
    if (!file) {
      this.setUrl(null);
      return;
    }

    // Hiện trước ngay từ máy người dùng, không phải chờ mạng
    const localUrl = URL.createObjectURL(file);
    this.showImage(localUrl);

    try {
      const result = await api.upload("/admin/uploads", file);
      this.url = result.url;
      this.showImage(ApiClient.assetUrl(result.url));
      URL.revokeObjectURL(localUrl);
      return result.url;
    } catch (err) {
      this.setUrl(null);
      this.input.value = "";
      toasts.error(`Tải ${this.label} thất bại`, err.message);
      return null;
    }
  }

  showImage(src) {
    if (!this.preview) return;
    this.preview.src = src;
    this.preview.hidden = false;
    if (this.empty) this.empty.hidden = true;
  }

  setUrl(url) {
    this.url = url;
    if (url) {
      this.showImage(ApiClient.assetUrl(url));
    } else if (this.preview) {
      this.preview.hidden = true;
      if (this.empty) this.empty.hidden = false;
    }
  }

  reset() {
    if (this.input) this.input.value = "";
    this.setUrl(null);
  }
}
