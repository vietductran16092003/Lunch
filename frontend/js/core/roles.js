/**
 * Bốn vai trò của hệ thống (mã 1.5).
 * Danh sách này phải khớp với `lunchapp/core/roles.py` bên backend.
 */
export const ROLES = ["employee", "coordinator", "treasurer", "admin"];

export const ROLE_LABELS = {
  employee: "Nhân viên",
  coordinator: "Người gom đơn",
  treasurer: "Thủ quỹ",
  admin: "Quản trị",
};

export const ROLE_HINTS = {
  employee: "Đặt món cho bản thân",
  coordinator: "Gom đơn, đặt gộp qua Grab",
  treasurer: "Quản lý quỹ, đối soát thu chi",
  admin: "Phân quyền, quản lý nhà hàng và món",
};

export const roleLabel = (role) => ROLE_LABELS[role] || role;

/** Thẻ nhãn vai trò, dùng chung ở nhiều màn hình. */
export function roleTagClass(role) {
  return `role-tag is-${role}`;
}
