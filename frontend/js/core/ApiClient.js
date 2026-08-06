import { API_BASE, ASSET_ROOT } from "./config.js";

/** Lỗi trả về từ backend, giữ nguyên mã HTTP để nơi gọi xử lý riêng. */
export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }

  /** true khi không kết nối được đến server (khác với server trả lỗi). */
  get isNetworkError() {
    return !this.status;
  }
}

/** Bọc fetch: luôn gửi cookie phiên, luôn ném ApiError khi thất bại. */
export class ApiClient {
  constructor(baseUrl = API_BASE) {
    this.baseUrl = baseUrl;
  }

  async request(path, options = {}) {
    let response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, {
        credentials: "include",
        ...options,
      });
    } catch (err) {
      throw new ApiError("Không kết nối được đến server", 0, null);
    }

    let data = null;
    try {
      data = await response.json();
    } catch (err) {
      data = null;
    }

    if (!response.ok) {
      throw new ApiError(
        (data && data.error) || "Yêu cầu không thành công",
        response.status,
        data
      );
    }
    return data;
  }

  get(path) {
    return this.request(path);
  }

  post(path, body) {
    return this.sendJson(path, "POST", body);
  }

  put(path, body) {
    return this.sendJson(path, "PUT", body);
  }

  delete(path) {
    return this.request(path, { method: "DELETE" });
  }

  sendJson(path, method, body) {
    return this.request(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
  }

  upload(path, file) {
    const form = new FormData();
    form.append("file", file);
    return this.request(path, { method: "POST", body: form });
  }

  /** Đổi đường dẫn tương đối của backend thành URL đầy đủ dùng được trong <img>. */
  static assetUrl(path) {
    if (!path) return "";
    if (/^https?:\/\//i.test(path)) return path;
    return `${ASSET_ROOT}${path}`;
  }
}

export const api = new ApiClient();
