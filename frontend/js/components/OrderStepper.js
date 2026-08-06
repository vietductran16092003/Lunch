import { Dom } from "../core/Dom.js";

/** Thanh tiến trình 4 bước của một đơn hàng. */
export class OrderStepper {
  static STEPS = [
    { key: "pending", label: "Chọn món", hint: "Đặt trước giờ chốt" },
    { key: "closed", label: "Đã chốt đơn", hint: "Không sửa được nữa" },
    { key: "ordered", label: "Đặt trên Grab", hint: "Chờ quán xác nhận" },
    { key: "completed", label: "Hoàn tất", hint: "Đã thanh toán" },
  ];

  constructor(containerId = "order-stepper") {
    this.container = Dom.byId(containerId);
  }

  /** currentIndex: 0..3, lấy từ order.step_index. */
  render(currentIndex = 0) {
    if (!this.container) return;
    Dom.clear(this.container);

    OrderStepper.STEPS.forEach((step, index) => {
      const done = index < currentIndex;
      const current = index === currentIndex;
      this.container.appendChild(this.buildStep(step, index, done, current));
    });
  }

  buildStep(step, index, done, current) {
    const li = Dom.el("li", {
      class: `step${done ? " is-done" : ""}${current ? " is-current" : ""}`,
      "aria-current": current ? "step" : null,
    });

    li.append(
      Dom.el("div", { class: "step-track" }, Dom.el("span")),
      Dom.el(
        "div",
        { class: "step-body" },
        Dom.el("span", {
          class: "step-mark",
          "aria-hidden": "true",
          text: done ? "✓" : String(index + 1),
        }),
        Dom.el(
          "div",
          {},
          Dom.el("div", { class: "step-label", text: `${index + 1}. ${step.label}` }),
          Dom.el("div", { class: "step-hint", text: done ? "Xong" : step.hint })
        )
      ),
      // Trình đọc màn hình nghe được trạng thái, không chỉ nhìn thấy màu
      Dom.srOnly(
        `Bước ${index + 1}: ${step.label} — ` +
          (done ? "đã xong" : current ? "đang thực hiện" : "chưa tới") + "."
      )
    );

    return li;
  }
}
