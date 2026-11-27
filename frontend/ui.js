export {api, pollJob} from './http.js';
export {identity, can} from './session.js';

export function esc(value) {
  return String(value ?? '—').replace(/[&<>"']/g, char => (
    {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]
  ));
}

export function tag(text, tone = '') {
  return '<span class="tag ' + esc(tone) + '">' + esc(text) + '</span>';
}

export function table(headers, rows) {
  if (!rows.length) return '<p class="empty">当前没有记录。完成上一步后再刷新此页。</p>';
  return '<div class="table-frame"><table><thead><tr>' +
    headers.map(label => '<th scope="col">' + esc(label) + '</th>').join('') +
    '</tr></thead><tbody>' + rows.map(row => '<tr>' + row.map(cell =>
      '<td>' + (cell?.html ?? esc(cell)) + '</td>').join('') + '</tr>').join('') +
    '</tbody></table></div>';
}

export function flash(root, message, tone = 'ok') {
  const node = root.matches?.('[data-status]') ? root : root.querySelector('[data-status]');
  if (!node) return;
  node.textContent = message;
  node.className = 'status ' + tone;
  node.hidden = !message;
}
