import { esc } from "/ui.js";
import { landmarks } from "../constants.js";

const edgeOffsets = { D4: [-4, 36], R2: [22, 26], A1: [0, -15], B2: [0, -14], C3: [0, -15], R1: [-12, 7] };

function edge(segment, move) {
  const [, x1, y1] = landmarks[segment.from_node];
  const [, x2, y2] = landmarks[segment.to_node];
  const [dx, dy] = edgeOffsets[segment.code] || [0, 0];
  const x = (x1 + x2) / 2 + dx;
  const y = (y1 + y2) / 2 + dy;
  const state = segment.code === move?.retire_code ? "retire" : segment.code === move?.deploy_code ? "deploy" : segment.state;
  const bend = `M ${x1} ${y1} Q ${x} ${y + dy} ${x2} ${y2}`;
  return `<g class="edge edge-${esc(state)}">
    <title>${esc(segment.code)} ${esc(segment.label)} ${esc(segment.length_m)} 米</title>
    <path d="${bend}"/>
    <rect x="${x - 19}" y="${y - 11}" width="38" height="22" rx="3"/>
    <text x="${x}" y="${y + 5}">${esc(segment.code)}</text>
  </g>`;
}

export function shoreMap(segments, move) {
  return `<div class="shore-map"><svg viewBox="0 0 750 316" role="img" aria-label="海滩铺毯路线拓扑">
    <path class="water" d="M0 287 Q130 252 226 271 T399 209 T565 201 T750 109 V316 H0Z"/>
    <path class="shore-contour" d="M0 279 Q130 244 226 263 T399 201 T565 193 T750 101"/>
    <path class="shore-contour" d="M0 264 Q126 232 222 250 T393 188 T565 180 T750 87"/>
    <path class="waterline" d="M356 291 Q449 248 507 253 T750 169 M444 306 Q562 270 750 226"/>
    <text class="sea-label" x="619" y="273">汀州湾</text>
    <text class="sea-label" x="16" y="33">北 ↑</text>
    ${segments.map(segment => edge(segment, move)).join("")}
    ${Object.values(landmarks).map(([label,x,y]) => `
      <circle class="landmark" cx="${x}" cy="${y}" r="7"/>
      <text class="landmark-label" x="${x}" y="${y - 23}">${label}</text>`).join("")}
  </svg><span class="map-key"><i></i> 已铺设 <i></i> 备用 / 拟撤</span></div>`;
}
