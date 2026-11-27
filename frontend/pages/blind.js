import { can, esc } from "/ui.js";
import { load } from "../store.js";
import {
  assessBlindTrial, blindBatch, openBlindBatch, recordBlindTrial,
  revealBlindBatch, runBlindTrial,
} from "../sand-api.js";
import { compactTime, marker, probability } from "../components/markers.js";
import { startAction } from "../components/feedback.js";

function progress(trials, key) {
  const done = trials.filter(item => item[key]).length;
  return `${done}/${trials.length}`;
}

function eligibleTrials(trials) {
  return trials.filter(item =>
    item.predicted_result === null && item.observed_result === null &&
    (item.blind_batch_code === null || item.blind_batch_code === undefined));
}

function openForm(trials) {
  if (!can("admin")) return "<p>此账号可以查看盲测进度与揭晓报告。</p>";
  const pool = eligibleTrials(trials);
  return `<form id="batch-form">
    <label>盲测名称<input name="title" required minlength="2" maxlength="120" placeholder="潮前滚轮盲测"></label>
    <label>参测测验（尚无预测和判读）
      <select name="trial_codes" multiple size="5" required>
        ${pool.map(item => `<option value="${esc(item.code)}">${esc(item.code)} · ${esc(item.segment_code)}</option>`).join("")}
      </select>
    </label>
    <button type="submit"${pool.length ? "" : " disabled"}>开测并锁定训练样本</button>
  </form>`;
}

function sealedActions(batch, item, mayEdit) {
  if (!mayEdit) return "";
  const predict = item.has_prediction ? "" : `
    <form data-blind-predict="${esc(item.code)}">
      <label>同时密封现场判读
        <select name="observed_result">
          <option value="">仅提交预测</option>
          <option value="clear">现场可通行</option>
          <option value="stuck">现场受阻</option>
        </select>
      </label>
      <button type="submit">用锁定样本推演</button>
    </form>`;
  const assess = item.has_observation ? "" : `
    <div class="trial-actions">
      <button type="button" data-assess="clear" data-code="${esc(item.code)}">现场可通行</button>
      <button class="quiet" type="button" data-assess="stuck" data-code="${esc(item.code)}">现场受阻</button>
    </div>`;
  return predict + assess;
}

function trialTable(batch, mayEdit, notice) {
  const sealed = batch.status === "sealed";
  const head = sealed
    ? "<tr><th>测验号码</th><th>毯段</th><th>时刻</th><th>预测</th><th>现场判读</th><th>操作</th></tr>"
    : "<tr><th>测验号码</th><th>毯段</th><th>时刻</th><th>模型判别</th><th>现场判读</th><th>可通行概率</th></tr>";
  const rows = batch.trials.map(item => {
    if (sealed) {
      return `<tr><td>${esc(item.code)}</td><td>${esc(item.segment_code)}</td>
        <td>${compactTime(item.observed_at)}</td>
        <td>${item.has_prediction ? "已密封" : "待推演"}</td>
        <td>${item.has_observation ? "已密封" : "待判读"}</td>
        <td>${sealedActions(batch, item, mayEdit)}</td></tr>`;
    }
    const falseClear = item.observed_result === "stuck" && item.predicted_result === "clear";
    return `<tr${falseClear ? ' class="false-clear"' : ""}><td>${esc(item.code)}</td>
      <td>${esc(item.segment_code)}</td><td>${compactTime(item.observed_at)}</td>
      <td>${marker("result", item.predicted_result)}</td>
      <td>${marker("result", item.observed_result)}</td>
      <td>${probability(item.clear_probability)}</td></tr>`;
  }).join("");
  return `<table class="sand-table"><thead>${head}</thead><tbody>${rows}</tbody></table>
    <p data-batch-notice class="sand-notice" role="status" hidden>${notice || ""}</p>`;
}

function recordForm(batch) {
  if (!can("operator", "admin")) return "";
  return `<form id="blind-record-form">
    <h3>向本批补录测验</h3>
    <div class="field-grid">
      <label>试踩毯段<input name="segment_code" required pattern="^[A-Z][0-9]{1,3}$" value="D4"></label>
      <label>坡度 (%)<input name="slope_pct" type="number" min="0" max="20" step="0.01" value="2.5" required></label>
      <label>湿度 (%)<input name="moisture_pct" type="number" min="0" max="100" step="0.01" value="22.3" required></label>
      <label>轮辙 (mm)<input name="rut_mm" type="number" min="0" max="100" step="0.01" value="3" required></label>
      <label>现场判读（可先密封）
        <select name="observed_result"><option value="">暂不判读</option><option value="clear">可通行</option><option value="stuck">受阻</option></select>
      </label>
    </div>
    <button type="submit">登记进盲测批次</button>
  </form>`;
}

export async function blindPage(root, selectedCode) {
  const {trials, blindBatches} = await load("trials", "blindBatches");
  const mayEdit = can("operator", "admin");
  const listed = blindBatches.batches || [];
  const chosen = selectedCode || listed[0]?.code;
  const batch = chosen ? await blindBatch(chosen) : null;
  root.innerHTML = `<div class="sand-content trial-page">
  <header class="sand-heading"><div>
    <p class="sand-overline">汀州海水浴场 / 模型盲测</p><h1>滚轮盲测批次</h1>
    <p>开测即锁定训练样本；预测与现场判读分别密封，全员齐备后统一揭晓，揭晓后样本才进入日常推演。</p>
  </div></header>
  <div class="field-grid">
    <section class="sand-panel field-form"><h2>新开盲测</h2>${openForm(trials)}
      <p data-open-notice class="sand-notice" role="status" hidden></p>
    </section>
    <section class="sand-panel trial-slip">
      <h2>批次列表</h2>
      ${listed.length ? `<label>选择批次<select data-batch-choice>${listed.map(item =>
        `<option value="${esc(item.code)}"${item.code === chosen ? " selected" : ""}>${esc(item.code)} · ${marker("state", item.status)}</option>`).join("")}</select></label>`
        : "<p>尚无盲测批次。</p>"}
      ${batch ? `<div class="trial-id">${esc(batch.code)} · ${esc(batch.title)} ${marker("state", batch.status)}</div>
        <dl class="trial-dl">
          <div><dt>开测锁定样本</dt><dd>${esc(batch.locked_sample_count)} 条</dd></div>
          <div><dt>参测测验</dt><dd>${esc(batch.trial_total)} 条</dd></div>
          <div><dt>开测时刻</dt><dd>${compactTime(batch.locked_at)}</dd></div>
          ${batch.status === "sealed"
            ? `<div><dt>预测进度</dt><dd>${progress(batch.trials, "has_prediction")}</dd></div>
               <div><dt>判读进度</dt><dd>${progress(batch.trials, "has_observation")}</dd></div>`
            : `<div><dt>受阻误判可通行</dt><dd><strong>${esc(batch.false_clear_count)}</strong> 次</dd></div>
               <div><dt>揭晓时刻</dt><dd>${compactTime(batch.revealed_at)}</dd></div>`}
        </dl>` : ""}
    </section>
  </div>
  ${batch ? `<section class="sand-roster">
    <div class="roster-title"><h2>${batch.status === "sealed" ? "密封进度" : "揭晓报告（仅此一份）"}</h2>
      ${batch.status === "sealed" && can("admin")
        ? `<button type="button" data-reveal>统一揭晓</button>` : ""}
    </div>
    ${batch.status === "revealed" ? `<p>共核对 ${esc(batch.report.checked)} 条，方向判对 ${esc(batch.report.correct_count)} 条，
       把现场受阻判成可通行 <strong>${esc(batch.report.false_clear_count)}</strong> 次
       ${batch.report.false_clear_codes.length ? "（" + batch.report.false_clear_codes.map(esc).join("、") + "）" : ""}。
       揭晓后这些判读已纳入日常推演训练。</p>` : ""}
    ${trialTable(batch, mayEdit)}
    ${batch.status === "sealed" ? recordForm(batch) : ""}
  </section>` : ""}
  </div>`;

  const openNotice = root.querySelector("[data-open-notice]");
  const open = root.querySelector("#batch-form");
  if (open) open.onsubmit = event => {
    event.preventDefault();
    startAction(event.submitter, openNotice, async () => {
      const formData = new FormData(open);
      const payload = {
        title: formData.get("title"),
        trial_codes: formData.getAll("trial_codes"),
      };
      const created = await openBlindBatch(payload);
      await blindPage(root, created.code);
    });
  };
  const choice = root.querySelector("[data-batch-choice]");
  if (choice) choice.onchange = event => blindPage(root, event.target.value);

  if (batch) {
    const batchNotice = root.querySelector("[data-batch-notice]");
    root.querySelectorAll("[data-blind-predict]").forEach(form => {
      form.onsubmit = event => {
        event.preventDefault();
        const code = form.dataset.blindPredict;
        const observed = new FormData(form).get("observed_result") || null;
        startAction(form.querySelector("button"), batchNotice, async () => {
          await runBlindTrial(batch.code, code, observed);
          await blindPage(root, batch.code);
        });
      };
    });
    root.querySelectorAll("[data-assess]").forEach(button => {
      button.onclick = () => startAction(button, batchNotice, async () => {
        await assessBlindTrial(batch.code, button.dataset.code, button.dataset.assess);
        await blindPage(root, batch.code);
      });
    });
    const reveal = root.querySelector("[data-reveal]");
    if (reveal) reveal.onclick = () => startAction(reveal, batchNotice, async () => {
      await revealBlindBatch(batch.code);
      await blindPage(root, batch.code);
    });
    const record = root.querySelector("#blind-record-form");
    if (record) record.onsubmit = event => {
      event.preventDefault();
      startAction(event.submitter, batchNotice, async () => {
        const values = Object.fromEntries(new FormData(record));
        values.observed_result = values.observed_result || null;
        await recordBlindTrial(batch.code, values);
        await blindPage(root, batch.code);
      });
    };
  }
}
