import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";
import { ROLES, ROLE_HINTS, roleLabel } from "../core/roles.js";
import { toasts } from "../core/ToastManager.js";

/**
 * Ma trận phân quyền: mỗi hàng một người, mỗi cột một vai trò (mã 1.5).
 *
 * Cố ý KHÔNG tự lưu khi tick. Phân quyền là thao tác nhạy cảm nên phải bấm
 * "Lưu" từng người, và hàng nào đang có thay đổi chưa lưu thì đánh dấu rõ.
 */
export class RoleMatrix {
  constructor(containerId = "role-matrix", { currentUserId = null } = {}) {
    this.container = Dom.byId(containerId);
    this.currentUserId = currentUserId;
    this.users = [];
    this.draft = new Map(); // userId -> Set(role) đang chỉnh
  }

  async load() {
    if (!this.container) return;
    try {
      const data = await api.get("/admin/users");
      this.users = data.users || [];
      this.draft.clear();
      this.render();
    } catch (err) {
      Dom.clear(this.container).appendChild(
        Dom.emptyState("⚠️", `Không tải được danh sách người dùng. ${err.message}`)
      );
    }
  }

  rolesOf(user) {
    return this.draft.get(user.id) || new Set(user.roles);
  }

  isDirty(user) {
    const draft = this.draft.get(user.id);
    if (!draft) return false;
    const original = new Set(user.roles);
    if (draft.size !== original.size) return true;
    return [...draft].some((r) => !original.has(r));
  }

  render() {
    Dom.clear(this.container);

    if (!this.users.length) {
      this.container.appendChild(Dom.emptyState("👥", "Chưa có người dùng nào."));
      return;
    }

    const tbody = Dom.el("tbody");
    this.users.forEach((user) => tbody.appendChild(this.buildRow(user)));

    const headCells = ROLES.map(
      (role) =>
        `<th scope="col" class="role-cell" title="${ROLE_HINTS[role]}">${roleLabel(role)}</th>`
    ).join("");

    const table = Dom.el("table", {
      html:
        "<caption>Tick vai trò rồi bấm Lưu ở từng người. Một người có thể mang nhiều vai trò.</caption>" +
        `<thead><tr><th scope="col">Người dùng</th>${headCells}` +
        '<th scope="col">Thao tác</th></tr></thead>',
    });
    table.appendChild(tbody);

    this.container.appendChild(Dom.el("div", { class: "table-wrap" }, table));
  }

  buildRow(user) {
    const row = Dom.el("tr");
    const isSelf = user.id === this.currentUserId;

    row.appendChild(
      Dom.el(
        "td",
        {},
        Dom.el("div", { style: "font-weight:600;", text: user.name }),
        Dom.el("div", { class: "subtitle", style: "margin:0; font-size:12.5px;", text: user.email }),
        isSelf ? Dom.el("div", { class: "role-tag", text: "Chính bạn" }) : null
      )
    );

    const save = Dom.el("button", {
      type: "button",
      text: "Lưu",
      disabled: true,
      "aria-label": `Lưu vai trò cho ${user.name}`,
    });

    ROLES.forEach((role) => {
      row.appendChild(this.buildRoleCell(user, role, isSelf, row, save));
    });

    save.addEventListener("click", () => this.save(user, save));

    const remove = Dom.el("button", {
      type: "button",
      class: "danger",
      text: "Xóa",
      disabled: isSelf,
      title: isSelf ? "Không thể tự xoá chính mình" : "",
      "aria-label": `Xoá tài khoản ${user.name}`,
    });
    remove.addEventListener("click", () => this.remove(user, remove));

    row.appendChild(
      Dom.el("td", { style: "display:flex; gap:6px; flex-wrap:wrap;" }, save, remove)
    );

    return row;
  }

  async remove(user, button) {
    if (!window.confirm(
      `Xoá hẳn tài khoản "${user.name}" (${user.email})? Không thể hoàn tác.`
    )) {
      return;
    }

    Dom.setBusy(button, true, `Đang xoá ${user.name}`);
    try {
      await api.delete(`/admin/users/${user.id}`);
      this.users = this.users.filter((u) => u.id !== user.id);
      this.draft.delete(user.id);
      toasts.success("Đã xoá tài khoản", user.name);
      this.render();
    } catch (err) {
      Dom.setBusy(button, false);
      toasts.error("Không xoá được", err.message);
    }
  }

  buildRoleCell(user, role, isSelf, row, save) {
    const active = this.rolesOf(user).has(role);

    // Không cho tự gỡ quyền quản trị của chính mình — chặn ngay ở giao diện,
    // backend cũng chặn lần nữa
    const lockSelfAdmin = isSelf && role === "admin";

    const input = Dom.el("input", {
      type: "checkbox",
      checked: active,
      disabled: lockSelfAdmin,
      "aria-label": `${roleLabel(role)} cho ${user.name}`,
    });
    input.checked = active;

    input.addEventListener("change", () => {
      const next = new Set(this.rolesOf(user));
      if (input.checked) next.add(role);
      else next.delete(role);
      this.draft.set(user.id, next);

      // Backend bắt mỗi người giữ ít nhất một vai trò, nên chặn ngay ở đây cho
      // người dùng biết trước khi bấm Lưu
      const dirty = this.isDirty(user);
      const empty = next.size === 0;
      row.classList.toggle("is-dirty", dirty);
      save.disabled = !dirty || empty;
      save.title = empty ? "Mỗi người phải giữ ít nhất một vai trò" : "";
    });

    const label = Dom.el(
      "label",
      {
        class: "role-check",
        title: lockSelfAdmin ? "Không thể tự gỡ quyền quản trị của chính mình" : ROLE_HINTS[role],
      },
      input
    );

    return Dom.el("td", { class: "role-cell" }, label);
  }

  async save(user, button) {
    const roles = [...this.rolesOf(user)];
    if (!roles.length) {
      toasts.warning("Mỗi người phải giữ ít nhất một vai trò");
      return;
    }

    Dom.setBusy(button, true, `Đang lưu vai trò cho ${user.name}`);
    try {
      const updated = await api.put(`/admin/users/${user.id}/roles`, { roles });
      // Cập nhật bản gốc để hàng hết trạng thái "chưa lưu"
      user.roles = updated.roles;
      this.draft.delete(user.id);
      toasts.success("Đã cập nhật vai trò", `${user.name}: ${updated.roles.map(roleLabel).join(", ") || "không có vai trò"}`);
      this.render();
    } catch (err) {
      Dom.setBusy(button, false);
      toasts.error("Không lưu được vai trò", err.message);
    }
  }
}
