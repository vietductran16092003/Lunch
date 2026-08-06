// Địa chỉ backend. Đổi ở đây là đổi cho toàn bộ giao diện.
export const API_BASE = "http://localhost:5000/api";

// Gốc để ghép đường dẫn ảnh do backend trả về (dạng /api/uploads/...)
export const ASSET_ROOT = API_BASE.replace(/\/api$/, "");
