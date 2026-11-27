import { can, esc } from "/ui.js";
import { load } from "../store.js";
import { createTrial, runTrial, confirmTrial } from "../sand-api.js";
import { compactTime, marker, probability } from "../components/markers.js";
import { startAction } from "../components/feedback.js";

function latestTrial(trials, code) {
  return trials.find(row => row.code === code) || trials[0];
}

function trialCard(row, mayEdit) {
  if (!row) return `<p>先登记一个毯段的滚轮测量，系统会在这里列出模型和现场结果。</p>`;
  return `<div class="trial-id">${esc(row.code)} · ${esc(row.segment_code)} <small>${compactTime(row.observed_at)}</small></div>
    <div class="trial-meters"><span>坡度 <strong>${esc(row.slope_pct)}%</strong></span><span>湿度 <strong>${esc(row.moisture_pct)}%</strong></span><span>轮辙 <strong>${esc(row.rut_mm)}mm</strong></span></div>
    <dl class="trial-dl"><div><dt>模型判别</dt><dd>${marker("result", row.predicted_result)} ${probability(row.clear_probability)}</dd></div>
    <div><dt>现场判读</dt><dd>${marker("result", row.observed_result)}</dd></div>
    <div><dt>拟合测验</dt><dd>${row.sample_count ?? "—"} 条</dd></div></dl>
    ${mayEdit && !row.observed_result ? `
      <div class="trial-actions">
      ${row.predicted_result ? '<button type="button" data-confirm="clear">现场可通行</button><button class="quiet" type="button" data-confirm="stuck">现场受阻</button>' : '<button type="button" data-run>用模型推演</button>'}
      </div>` : ""}`;
}

export async function trialsPage(root, selected) {
  const {map, trials} = await load("map", "trials");
  const mayEdit = can("operator", "admin");
  const row = latestTrial(trials, selected || "TR-D4-DAWN");
  root.innerHTML = `<div class="sand-content trial-page">
  <header class="sand-heading"><div><p class="sand-overline">汀州海水浴场 / 滚轮通行</p><h1>通行试验</h1><p>先记录三项实测，再跑通行分类并登记独立的现场结果。</p></div></header>
  <div class="field-grid">
    <section class="sand-panel field-form"><h2>新测验</h2>
      ${mayEdit ? `<form id="trial-form"><label>试踩毯段<select name="segment_code">${map.segments.map(item => `<option value="${esc(item.code)}"${item.code === "D4" ? " selected" : ""}>${esc(item.code)} · ${esc(item.label)}</option>`).join("")}</select></label>
      <label>纵向坡度 (%)<input name="slope_pct" type="number" min="0" max="20" step="0.01" value="2.5" required></label>
      <label>砂面湿度 (%)<input name="moisture_pct" type="number" min="0" max="100" step="0.01" value="22.3" required></label>
      <label>轮辙深度 (mm)<input name="rut_mm" type="number" min="0" max="100" step="0.01" value="3" required></label>
      <button type="submit">登记测验</button></form>` : "<p>此账号可以查看通行记录。</p>"}
    </section>
    <section class="sand-panel trial-slip"><h2>测验记录</h2><label>选择测验
      <select id="sample-select">${trials.map(item => `<option value="${esc(item.code)}"${row?.code === item.code ? " selected" : ""}>${esc(item.code)} · ${esc(item.segment_code)}</option>`).join("")}</select></label>
      ${trialCard(row, mayEdit)}
      <p data-notice class="sand-notice" role="status" hidden></p>
    </section>
  </div>
  <section class="sand-roster"><div class="roster-title"><h2>现场试验记录</h2><a href="#moves" class="sand-link">前往换段推演 →</a></div>
  <table class="sand-table"><thead><tr><th>段号</th><th>测验号码</th><th>时刻</th><th>模型</th><th>现场</th></tr></thead><tbody>
  ${trials.map(item => `<tr><th>${esc(item.segment_code)}</th><td>${esc(item.code)}</td><td>${compactTime(item.observed_at)}</td><td>${marker("result", item.predicted_result)}</td><td>${marker("result", item.observed_result)}</td></tr>`).join("")}
  </tbody></table></section></div>`;
  const notice = root.querySelector("[data-notice]");
  root.querySelector("#sample-select").onchange = event => trialsPage(root, event.target.value);
  const form = root.querySelector("#trial-form");
  if (form) form.onsubmit = event => {
    event.preventDefault();
    startAction(event.submitter, notice, async () => {
      const values = Object.fromEntries(new FormData(form));
      const created = await createTrial(values);
      await trialsPage(root, created.code);
    });
  };
  const prediction = root.querySelector("[data-run]");
  if (prediction) prediction.onclick = () => startAction(prediction, notice, async () => {
    await runTrial(row.code);
    await trialsPage(root, row.code);
  });
  root.querySelectorAll("[data-confirm]").forEach(button => {
    button.onclick = () => startAction(button, notice, async () => {
      await confirmTrial(row.code, button.dataset.confirm);
      await trialsPage(root, row.code);
    });
  });
}
