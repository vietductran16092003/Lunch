/**
 * Cảnh báo dinh dưỡng/dị ứng rule-based (Phase 5): dò từ khoá trong tên, mô tả,
 * thẻ của món — không có dữ liệu dinh dưỡng thật, chỉ là gợi ý để nhân viên
 * tự cân nhắc trước khi đặt.
 */
const RULES = [
  { keywords: ["tôm", "cua", "mực", "cá", "hải sản", "sò", "ốc"], label: "Hải sản", type: "warning" },
  { keywords: ["đậu phộng", "lạc"], label: "Đậu phộng", type: "warning" },
  { keywords: ["sữa", "phô mai", "bơ", "kem"], label: "Sữa/bơ", type: "info" },
  { keywords: ["cay", "ớt", "sa tế"], label: "Cay", type: "info" },
  { keywords: ["chay"], label: "Chay", type: "success" },
  { keywords: ["gluten", "bột mì", "mì"], label: "Gluten", type: "info" },
];

export const NutritionWarnings = {
  /** Trả về [{label, type}] các cảnh báo khớp với món này. */
  detect(item) {
    const haystack = [item.name, item.description, item.tags]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return RULES.filter((rule) => rule.keywords.some((k) => haystack.includes(k)))
      .map((rule) => ({ label: rule.label, type: rule.type }));
  },
};
