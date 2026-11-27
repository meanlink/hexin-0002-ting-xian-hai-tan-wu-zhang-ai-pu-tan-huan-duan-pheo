import app from './app.js';
import {api, esc, flash} from './ui.js';
import {identity, roles, setIdentity} from './session.js';

const shell = document.querySelector('#shell');
document.title = app.title;

function signIn() {
  shell.innerHTML = '<section class="login-layout"><header class="login-brand"><h1>' +
    esc(app.title) + '</h1><p>' + esc(app.subtitle) + '</p></header>' +
    '<form id="login" class="login-form"><h2>登录工作台</h2>' +
    '<label>账号<input name="email" type="email" autocomplete="username" value="operator@demo.test" required></label>' +
    '<label>密码<input name="password" type="password" autocomplete="current-password" value="Demo2026!" required></label>' +
    '<button type="submit">登录</button><p role="status" data-status hidden></p></form></section>';
  const form = shell.querySelector('form');
  form.onsubmit = async event => {
    event.preventDefault();
    const submit = form.querySelector('button');
    submit.disabled = true;
    try {
      const user = await api('/auth/login', {method: 'POST', body: Object.fromEntries(new FormData(form))});
      setIdentity(user);
      render();
    } catch (error) {
      flash(form, error.message, 'error');
    } finally { submit.disabled = false; }
  };
}

async function render() {
  const user = identity();
  if (!user) return signIn();
  const active = app.pages.find(page => '#' + page.id === location.hash) ?? app.pages[0];
  shell.innerHTML = '<header class="masthead"><div class="brand"><strong>' + esc(app.title) +
    '</strong><span>' + esc(app.subtitle) + '</span></div><div class="identity"><span>' +
    esc(roles[user.role] ?? user.role) + '</span><button type="button" data-logout>退出</button></div></header>' +
    '<nav class="main-nav" aria-label="业务模块">' + app.pages.map(page =>
    '<a href="#' + esc(page.id) + '"' + (page === active ? ' aria-current="page"' : '') +
    '>' + esc(page.title) + '</a>').join('') + '</nav><section class="page" id="view" tabindex="-1"></section>';
  shell.querySelector('[data-logout]').onclick = () => {
    setIdentity(null);
    signIn();
  };
  const view = shell.querySelector('#view');
  try {
    await active.render(view);
    view.dataset.ready = 'true';
  } catch (error) {
    if (error.status === 401) {
      setIdentity(null);
      signIn();
      return;
    }
    view.textContent = error.message;
    view.classList.add('error');
    const retry = document.createElement('button');
    retry.textContent = '重新加载';
    retry.onclick = render;
    view.append(' ', retry);
    view.dataset.ready = 'error';
  }
}

addEventListener('hashchange', render);
render();
