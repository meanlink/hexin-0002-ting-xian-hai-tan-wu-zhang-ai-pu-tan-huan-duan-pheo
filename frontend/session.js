export const roles = Object.freeze({viewer: '查阅', operator: '操作员', admin: '负责人'});
export const jobStates = Object.freeze({queued: '排队中', running: '计算中', done: '已完成', failed: '失败'});
const sessionKey = 'hexin.session';

export function identity() {
  try { return JSON.parse(sessionStorage.getItem(sessionKey)); }
  catch { return null; }
}

export function setIdentity(user) {
  if (user) sessionStorage.setItem(sessionKey, JSON.stringify(user));
  else sessionStorage.removeItem(sessionKey);
}

export function can(...allowed) {
  return allowed.includes(identity()?.role);
}
