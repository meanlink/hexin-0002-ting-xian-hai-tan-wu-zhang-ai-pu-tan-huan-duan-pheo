import {identity} from './session.js';

export async function api(path, options = {}) {
  const {body, ...init} = options;
  const token = identity()?.token;
  const headers = new Headers(init.headers);
  if (token) headers.set('Authorization', 'Bearer ' + token);
  if (body !== undefined) headers.set('Content-Type', 'application/json');
  const result = await fetch('/api' + path, {
    ...init, headers, body: body === undefined ? undefined : JSON.stringify(body)
  });
  const data = await result.json();
  if (!result.ok) {
    const detail = Array.isArray(data.detail) ?
      data.detail.map(item => item.loc?.join('.') + ' ' + item.msg).join('，') : data.detail;
    const error = new Error(detail || '操作失败');
    error.status = result.status;
    throw error;
  }
  return data;
}

export async function pollJob(id) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const job = await api('/jobs/' + encodeURIComponent(id));
    if (job.status === 'done') return job.result;
    if (job.status === 'failed') throw new Error(job.error || '模型计算失败');
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  throw new Error('计算仍在运行，请稍后查看');
}
