import { esc } from "/ui.js";
import { load } from "../store.js";
import { marker } from "../components/markers.js";
import { paths } from "../components/paths.js";
import { shoreMap } from "../components/shore-map.js";

export async function segmentsPage(root) {
  const {map} = await load("map");
  const laid = map.segments.filter(segment => segment.state === "laid");
  const distance = laid.reduce((sum, segment) => sum + Number(segment.length_m), 0).toFixed(1);
  root.innerHTML = `<div class="sand-content chart-page">
  <header class="sand-heading">
    <div><p class="sand-overline">汀州海水浴场 / 值班潮图</p><h1>分段示意</h1><p>按实铺状态查看入滩、观察和救援通路。待换毯段用虚线标记。</p></div>
    <div class="chart-stat"><strong>${esc(distance)}</strong><span>米已铺 · ${laid.length} 段</span></div>
  </header>
  <div class="chart-grid">
    ${shoreMap(map.segments)}
    <aside class="sand-panel route-panel"><h2>通行关口</h2>${paths(map.routes)}
    <a class="sand-link" href="#trials">登记滚轮测验 →</a></aside>
  </div>
  <section class="sand-roster"><div class="roster-title"><h2>铺毯分段表</h2><span>${map.segments.length} 段</span></div>
    <table class="sand-table"><thead><tr><th>段号</th><th>位置</th><th>长度 / 米</th><th>用途</th><th>状态</th></tr></thead><tbody>
    ${map.segments.map(segment => `<tr><th>${esc(segment.code)}</th><td>${esc(segment.label)}</td><td>${esc(segment.length_m)}</td><td>${marker("priority", segment.priority)}</td><td>${marker("state", segment.state)}</td></tr>`).join("")}
    </tbody></table>
  </section></div>`;
}
