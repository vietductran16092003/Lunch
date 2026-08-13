/**
 * Ba vai trò của hệ thống (mã 1.5).
 * Danh sách này phải khớp với `lunchapp/core/roles.py` bên backend.
 */
export const ROLES = ["employee", "treasurer", "admin"];

export const ROLE_LABELS = {
  employee: "Nhân viên",
  treasurer: "Thủ quỹ",
  admin: "Quản trị",
};

export const ROLE_HINTS = {
  employee: "Đặt món cho bản thân",
  treasurer: "Quản lý quỹ, đối soát thu chi",
  admin: "Phân quyền, quản lý nhà hàng, món và gom đơn",
};

export const roleLabel = (role) => ROLE_LABELS[role] || role;

/** true nếu `user` (đối tượng trả về từ /api/me) mang ít nhất một trong các vai trò. */
export function hasAnyRole(user, roles) {
  if (!user || !Array.isArray(user.roles)) return false;
  return roles.some((role) => user.roles.includes(role));
}

/** Thẻ nhãn vai trò, dùng chung ở nhiều màn hình. */
export function roleTagClass(role) {
  return `role-tag is-${role}`;
}
