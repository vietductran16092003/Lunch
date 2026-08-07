import { api } from "../core/ApiClient.js";
import { Dom } from "../core/Dom.js";

/** Nút chat nổi ở góc màn hình, hỏi đáp nhanh qua /api/ai/chat (mã Phase 3). */
export class Chatbot {
  mount() {
    if (Dom.byId("chatbot-toggle")) return;

    const toggle = Dom.el(
      "button",
      { id: "chatbot-toggle", class: "chatbot-toggle", type: "button", title: "Hỏi trợ lý" },
      "💬"
    );
    const panel = Dom.el("div", { id: "chatbot-panel", class: "chatbot-panel is-hidden" });
    const log = Dom.el("div", { id: "chatbot-log", class: "chatbot-log" });
    const input = Dom.el("input", {
      id: "chatbot-input",
      type: "text",
      placeholder: "Hỏi về thực đơn, đơn hàng, giờ chốt…",
    });
    const send = Dom.el("button", { type: "button", class: "subtle", text: "Gửi" });

    panel.append(
      Dom.el("div", { class: "chatbot-head" }, "Trợ lý Lunch App"),
      log,
      Dom.el("div", { class: "chatbot-input-row" }, input, send)
    );

    document.body.append(toggle, panel);

    toggle.addEventListener("click", () => {
      panel.classList.toggle("is-hidden");
      if (!panel.classList.contains("is-hidden") && !log.childElementCount) {
        this.appendMessage(log, "bot", "Chào bạn! Hỏi mình về thực đơn, đơn hàng hay giờ chốt nhé.");
      }
    });

    const submit = () => this.ask(input, log);
    send.addEventListener("click", submit);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") submit();
    });
  }

  async ask(input, log) {
    const text = input.value.trim();
    if (!text) return;
    this.appendMessage(log, "user", text);
    input.value = "";

    try {
      const data = await api.post("/ai/chat", { message: text });
      this.appendMessage(log, "bot", data.reply);
    } catch (err) {
      this.appendMessage(log, "bot", "Xin lỗi, mình chưa trả lời được lúc này.");
    }
  }

  appendMessage(log, from, text) {
    log.appendChild(Dom.el("div", { class: `chatbot-msg is-${from}`, text }));
    log.scrollTop = log.scrollHeight;
  }
}
