import { esc } from "/ui.js";

export function paths(routes) {
  return `<ol class="route-list">${routes.map(route => `
    <li class="${route.connected ? "route-intact" : "route-broken"}">
      <span class="route-glyph" aria-hidden="true">${route.purpose === "rescue" ? "✚" : "↝"}</span>
      <div><strong>${esc(route.label)}</strong>
      <small>${route.connected ? route.segments.map(esc).join(" → ") : "路线中断，暂不可签发"}</small></div>
      <span class="route-label">${route.connected ? "连通" : "中断"}</span>
    </li>`).join("")}</ol>`;
}
