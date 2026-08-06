/**
 * Điểm vào duy nhất của giao diện.
 * Mỗi trang HTML khai báo <body data-page="..."> và file này dựng đúng lớp trang.
 */

import { AdminPage } from "./pages/AdminPage.js";
import {
  ForgotPasswordPage,
  LoginPage,
  RegisterPage,
  ResetPasswordPage,
} from "./pages/AuthPages.js";
import { HistoryPage } from "./pages/HistoryPage.js";
import { MenuPage } from "./pages/MenuPage.js";

const PAGES = {
  menu: MenuPage,
  history: HistoryPage,
  admin: AdminPage,
  login: LoginPage,
  register: RegisterPage,
  "forgot-password": ForgotPasswordPage,
  "reset-password": ResetPasswordPage,
};

function bootstrap() {
  const name = document.body.dataset.page;
  const PageClass = PAGES[name];

  if (!PageClass) {
    console.warn(`Không tìm thấy lớp trang cho data-page="${name}"`);
    return;
  }

  new PageClass().start().catch((err) => {
    console.error(`Lỗi khi khởi tạo trang ${name}:`, err);
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootstrap);
} else {
  bootstrap();
}
