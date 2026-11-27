import { can, esc } from "/ui.js";
import { load } from "../store.js";
import { handoverMove } from "../sand-api.js";
import { marker, compactTime } from "../components/markers.js";
import { startAction } from "../components/feedback.js";
import { paths } from "../components/paths.js";

export async function handoverPage(root, handedCode) {
  const {map, moves} = await load("map", "moves");
  const signed = moves.filter(order => order.state !== "draft").sort((a, b) => (b.signed_at || "").localeCompare(a.signed_at || ""));
  const latest = signed.find(order => order.code === handedCode) || signed[0];
  const pending = signed.filter(order => order.state === "approved");
  root.innerHTML = `<div class="sand-content handover-page">
  <header class="sand-heading"><div><p class="sand-overline">汀州海水浴场 / 当班记录</p><h1>值班交接</h1><p>从这里交接已签发的换段令，接班时一并核对实铺通路。</p></div>
  <div class="chart-stat"><strong>${pending.length}</strong><span>待交班</span></div></header>
  <div class="handover-grid">
  <section class="sand-panel handover-slip"><h2>最新交接单</h2>
    ${latest ? `<article><time>${esc(latest.tide_window)}</time><p class="handover-path">${esc(latest.retire_code)} → ${esc(latest.deploy_code)}</p>
      <p>${marker("state", latest.state)} <span>${esc(latest.code)}</span></p>
      <dl><dt>签发</dt><dd>${esc(latest.signatory)} · ${compactTime(latest.signed_at)}</dd>
      <dt>接班</dt><dd>${esc(latest.handed_to)} · ${compactTime(latest.handed_at)}</dd>
      <dt>现场备注</dt><dd>${esc(latest.remarks || "—")}</dd></dl></article>` :
      '<p>还没有已签发的换段令。</p><a href="#moves" class="sand-link">前往换段推演 →</a>'}
  </section>
  <section class="sand-panel"><h2>实铺通路</h2>${paths(map.routes)}
  ${can("operator", "admin") && pending.length ? `<form id="handover-form">
    <label>当班换段令<select name="order">${pending.map(order => `<option value="${esc(order.code)}">${esc(order.retire_code)} → ${esc(order.deploy_code)} · ${esc(order.tide_window)}</option>`).join("")}</select></label>
    <label>接班人<input name="recipient" minlength="2" maxlength="80" required placeholder="救生岗 周班长"></label>
    <button type="submit">登记交班</button>
  </form>` : ""}<p data-notice class="sand-notice" role="status" hidden></p>
  </section>
  </div>
  <section class="sand-roster"><div class="roster-title"><h2>换段交接簿</h2><span>${signed.length} 令</span></div>
  ${signed.length ? `<table class="sand-table"><thead><tr><th>潮窗</th><th>换段</th><th>签发人</th><th>接班人</th><th>记录</th></tr></thead><tbody>
  ${signed.map(order => `<tr><th>${esc(order.tide_window)}</th><td>${esc(order.retire_code)} → ${esc(order.deploy_code)}</td><td>${esc(order.signatory)}</td><td>${esc(order.handed_to)}</td><td>${marker("state", order.state)}</td></tr>`).join("")}
  </tbody></table>` : '<p>签发换段令后，交接单将进入此表。</p>'}
  </section></div>`;
  const form = root.querySelector("#handover-form");
  if (form) form.onsubmit = event => {
    event.preventDefault();
    startAction(event.submitter, root.querySelector("[data-notice]"), async () => {
      const {order, recipient} = Object.fromEntries(new FormData(form));
      await handoverMove(order, recipient);
      await handoverPage(root, order);
    });
  };
}
