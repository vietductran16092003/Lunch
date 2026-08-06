/** Tiện ích thao tác DOM dùng chung. */
export class Dom {
  /** Tạo phần tử gọn: el("div", {class:"card"}, "nội dung") */
  static el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);

    Object.entries(attrs).forEach(([key, value]) => {
      if (value === null || value === undefined || value === false) return;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key === "html") node.innerHTML = value;
      else if (key === "style") node.style.cssText = value;
      else if (key.startsWith("on") && typeof value === "function") {
        node.addEventListener(key.slice(2).toLowerCase(), value);
      } else if (value === true) node.setAttribute(key, "");
      else node.setAttribute(key, value);
    });

    children.flat().forEach((child) => {
      if (child === null || child === undefined || child === false) return;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    });

    return node;
  }

  static byId(id) {
    return document.getElementById(id);
  }

  static setText(target, text) {
    const node = typeof target === "string" ? Dom.byId(target) : target;
    if (node) node.textContent = text;
  }

  static clear(node) {
    if (node) node.innerHTML = "";
    return node;
  }

  /** Chỉ đọc được bằng trình đọc màn hình. */
  static srOnly(text) {
    return Dom.el("span", { class: "sr-only", text });
  }

  /** Khóa nút và hiện vòng quay trong lúc chờ server. */
  static setBusy(button, busy, busyLabel) {
    if (!button) return;
    if (busy) {
      button.dataset.originalLabel = button.textContent;
      button.classList.add("is-busy");
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      if (busyLabel) button.setAttribute("aria-label", busyLabel);
    } else {
      button.classList.remove("is-busy");
      button.disabled = false;
      button.removeAttribute("aria-busy");
      button.removeAttribute("aria-label");
      if (button.dataset.originalLabel) button.textContent = button.dataset.originalLabel;
    }
  }

  /** Trạng thái rỗng dùng chung cho mọi danh sách. */
  static emptyState(icon, message, action = null) {
    return Dom.el(
      "div",
      { class: "empty-state" },
      Dom.el("div", { class: "icon", "aria-hidden": "true", text: icon }),
      message,
      action ? Dom.el("div", { class: "empty-action" }, action) : null
    );
  }

  /** Hộp thông báo trong trang (info / warning / success / error). */
  static notice(type, title, body, extra = null) {
    return Dom.el(
      "div",
      { class: `notice ${type}`, role: "status" },
      Dom.el(
        "div",
        {},
        title ? Dom.el("strong", { text: title }) : null,
        body || null,
        extra
      )
    );
  }
}
