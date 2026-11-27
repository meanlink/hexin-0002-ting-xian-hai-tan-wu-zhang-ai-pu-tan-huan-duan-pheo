import { can, esc } from "/ui.js";
import { load } from "../store.js";
import { approveMove, moveDetails, proposeMove } from "../sand-api.js";
import { marker, probability } from "../components/markers.js";
import { startAction } from "../components/feedback.js";
import { paths } from "../components/paths.js";
import { shoreMap } from "../components/shore-map.js";

function option(item, text) {
  return `<option value="${esc(item.code)}">${esc(text)}</option>`;
}

function moveForm(map, trials, mayEdit) {
  if (!mayEdit) return "<p>此账号可以查看草拟换段与路线检查。</p>";
  const qualified = trials.filter(item => item.predicted_result === "clear" && item.observed_result === "clear");
  return `<form id="move-form">
      <label>撤下毯段<select name="retire_code">${map.segments.filter(item => item.state === "laid").map(item => option(item, item.code + " · " + item.label)).join("")}</select></label>
      <label>改铺备用段<select name="deploy_code">${map.segments.filter(item => item.state === "standby").map(item => option(item, item.code + " · " + item.label)).join("")}</select></label>
      <label>该段的通行测验<select name="trial_code" required>${qualified.map(item => option(item, item.segment_code + " / " + item.code + " · " + probability(item.clear_probability))).join("")}</select></label>
      ${qualified.length ? "" : '<a href="#trials">先完成备用段实测 →</a>'}
      <div class="window-grid"><label>起始时间<input type="time" name="from" value="10:10" required></label><label>截止时间<input type="time" name="to" value="10:35" required></label></div>
      <label>交班备注<input name="remarks" maxlength="220" placeholder="木道东侧见证员"></label>
      <button type="submit"${qualified.length ? "" : " disabled"}>保存草拟并校核通路</button>
    </form>`;
}

export async function movesPage(root, code) {
  const {map, trials, moves} = await load("map", "trials", "moves");
  const selected = code || moves[0]?.code;
  const move = selected ? await moveDetails(selected) : null;
  const mayEdit = can("operator", "admin");
  root.innerHTML = `<div class="sand-content move-page">
  <header class="sand-heading"><div><p class="sand-overline">汀州海水浴场 / 潮窗换段</p><h1>换段推演</h1><p>给通过滚轮试验的备用段安排换段，签发前校验两条通路。</p></div></header>
  <div class="move-grid">
    <section class="sand-panel move-form"><h2>草拟换段令</h2>${moveForm(map, trials, mayEdit)}
      <p data-form-status class="sand-notice" role="status" hidden></p>
    </section>
    <section class="sand-panel move-preview">
      <div class="roster-title"><h2>替换后的通路</h2>${move ? marker("state", move.state) : ""}</div>
      ${moves.length ? `<label>查看换段令<select data-move-choice>${moves.map(item => `<option value="${esc(item.code)}"${item.code === selected ? " selected" : ""}>${esc(item.retire_code)} → ${esc(item.deploy_code)} · ${esc(item.tide_window)}</option>`).join("")}</select></label>` : '<p>保存草拟令后，地图将标记拟撤和拟铺段。</p>'}
      ${shoreMap(map.segments, move)}
      ${paths(move?.routes || map.routes)}
      ${move?.state === "draft" && can("admin") ? '<button type="button" data-approve>签发换段令</button>' : ""}
      <p data-approve-status class="sand-notice" role="status" hidden></p>
    </section>
  </div>
  </div>`;
  const form = root.querySelector("#move-form");
  if (form) {
    const evidence = form.elements.trial_code;
    const options = [...evidence.options];
    function filterEvidence() {
      const segment = form.elements.deploy_code.value;
      evidence.replaceChildren(...options.filter(item => item.textContent.startsWith(segment + " / ")));
    }
    form.elements.deploy_code.onchange = filterEvidence;
    filterEvidence();
    form.onsubmit = event => {
      event.preventDefault();
      startAction(event.submitter, root.querySelector("[data-form-status]"), async () => {
        const {from, to, ...formData} = Object.fromEntries(new FormData(form));
        const next = await proposeMove({...formData, tide_window: from + "–" + to});
        await movesPage(root, next.code);
      });
    };
  }
  const select = root.querySelector("[data-move-choice]");
  if (select) select.onchange = event => movesPage(root, event.target.value);
  const approve = root.querySelector("[data-approve]");
  if (approve) approve.onclick = () => startAction(approve, root.querySelector("[data-approve-status]"), async () => {
    await approveMove(move.code);
    await movesPage(root, move.code);
  });
}
