const STORAGE_KEY = "lunchapp-theme";

/** Chế độ sáng/tối, lưu lại giữa các lần tải trang. */
export const Theme = {
  get() {
    return localStorage.getItem(STORAGE_KEY) === "dark" ? "dark" : "light";
  },

  set(theme) {
    const value = theme === "dark" ? "dark" : "light";
    localStorage.setItem(STORAGE_KEY, value);
    Theme.apply(value);
  },

  toggle() {
    const next = Theme.get() === "dark" ? "light" : "dark";
    Theme.set(next);
    return next;
  },

  apply(theme) {
    document.documentElement.setAttribute("data-theme", theme === "dark" ? "dark" : "light");
  },
};

Theme.apply(Theme.get());
