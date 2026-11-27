import { esc } from "/ui.js";
import { names } from "../constants.js";

export function marker(category, value) {
  const name = names[category]?.[value];
  return `<span class="seal seal-${esc(value || "none")}">${esc(name || "未登记")}</span>`;
}

export const probability = value =>
  value === null || value === undefined ? "—" : `${(Number(value) * 100).toFixed(1)}%`;

export const compactTime = value =>
  value ? new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai", month: "numeric", day: "numeric",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23"
  }).format(new Date(value)) : "—";
