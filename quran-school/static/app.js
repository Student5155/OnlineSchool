'use strict';
/* Каркас приложения: запросы к серверу, навигация, общие элементы. Страницы — в pages.js. */

const ICONS = {
  home: '<path d="M3.5 10.5 12 3.5l8.5 7V20a1 1 0 0 1-1 1H15v-6H9v6H4.5a1 1 0 0 1-1-1z"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18.5 14.6c1.9.8 3 2.6 3 5.4"/>',
  book: '<path d="M12 6.5C10.5 5 8 4.5 4 4.5v13c4 0 6.5.5 8 2 1.5-1.5 4-2 8-2v-13c-4 0-6.5.5-8 2z"/><path d="M12 6.5v13"/>',
  wallet: '<path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H18v3"/><path d="M3 7.5V17a3 3 0 0 0 3 3h13a2 2 0 0 0 2-2v-8a2 2 0 0 0-2-2H5.5A2.5 2.5 0 0 1 3 7.5z"/><path d="M16.5 14h.01"/>',
  more: '<path d="M5 12h.01M12 12h.01M19 12h.01" stroke-width="3"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  chev: '<path d="m9 5 7 7-7 7"/>',
  back: '<path d="M15 5l-7 7 7 7"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  bell: '<path d="M6 16v-5a6 6 0 1 1 12 0v5l1.5 2h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
  alert: '<path d="M12 4 2.5 20h19z"/><path d="M12 10v4.5M12 17.3v.2"/>',
  phone: '<path d="M5 4h4l1.5 4.5-2 1.5a12 12 0 0 0 5.5 5.5l1.5-2L20 15v4a1 1 0 0 1-1 1C10.7 20 4 13.3 4 5a1 1 0 0 1 1-1z"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  logout: '<path d="M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4"/><path d="M15 8l4 4-4 4M19 12H9"/>',
  archive: '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v9a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9M10 13h4"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  calendar: '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
  inbox: '<path d="M3 13l3-8h12l3 8v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M3 13h5l1 3h6l1-3h5"/>',
  settings: '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
  coins: '<rect x="3" y="6" width="18" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M6.5 9.5v.01M17.5 14.5v.01"/>',
  user: '<circle cx="12" cy="8" r="3.5"/><path d="M5 20c0-3.9 3.1-6.5 7-6.5s7 2.6 7 6.5"/>',
  history: '<path d="M4 12a8 8 0 1 0 2.5-5.8L4 8.5"/><path d="M4 4v4.5h4.5M12 8v4l3 2"/>',
  star: '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8L3.5 9.7l5.9-.9z"/>',
  msg: '<path d="M4 5h16v11H9l-5 4z"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
};
const icon = (name, cls) => `<svg class="ic ${cls || ''}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ''}</svg>`;
const LOGO = '<svg width="44" height="44" viewBox="8 8 32 32" fill="none" stroke="#fff" stroke-width="1.9" stroke-linejoin="round" aria-hidden="true"><rect x="13" y="13" width="22" height="22"/><rect x="13" y="13" width="22" height="22" transform="rotate(45 24 24)"/></svg>';

const S = { me: null, meta: null, navCount: 0, seq: 0 };
const $ = (sel, el) => (el || document).querySelector(sel);
const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// ---------- форматирование ----------
const MON = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
const MONG = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
const DOW = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб'];
const DOWF = ['воскресенье', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота'];
const ISO_DOW = ['', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'];
const pd = (s) => { const [y, m, d] = String(s).slice(0, 10).split('-').map(Number); return new Date(y, m - 1, d); };
const isoD = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const fmtD = (s) => { if (!s) return ''; const d = pd(s); return `${d.getDate()} ${MON[d.getMonth()]}`; };
const fmtDL = (s) => { const d = pd(s); return `${DOWF[d.getDay()]}, ${d.getDate()} ${MONG[d.getMonth()]}`; };
const money = (n) => Number(n || 0).toLocaleString('ru-RU').replace(/ | /g, ' ') + ' ' + ((S.me && S.me.currency) || '₽');
const plural = (n, one, few, many) => { const a = Math.abs(n) % 100, b = a % 10; return a > 10 && a < 20 ? many : b === 1 ? one : b >= 2 && b <= 4 ? few : many; };
const nWord = (n, one, few, many) => `${n}\u00a0${plural(n, one, few, many)}`;
const ageText = (a) => (a == null ? '' : nWord(a, 'год', 'года', 'лет'));
const genderGroup = (g) => (g === 'f' ? 'женская' : 'мужская');
function schedText(sched) {
  const byTime = {};
  (sched || []).forEach((s) => { (byTime[s.t] = byTime[s.t] || []).push(ISO_DOW[s.d]); });
  return Object.keys(byTime).map((t) => `${byTime[t].join(', ')} ${t}`).join(' · ') || 'расписание не задано';
}
const GRADE = { 5: 'отлично', 4: 'хорошо', 3: 'удовл.' };
const METHOD = { cash: 'наличные', transfer: 'перевод', card: 'карта' };
const ROLE = { owner: 'владелец', admin: 'администратор', teacher: 'учитель' };
const isStaff = () => S.me && S.me.role !== 'teacher';
const isOwner = () => S.me && S.me.role === 'owner';

// ---------- сервер ----------
async function api(method, url, body) {
  const res = await fetch('/api' + url, {
    method, credentials: 'same-origin',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch (e) { /* пустой ответ */ }
  if (res.status === 401 && S.me) { S.me = null; renderLogin(); throw new Error('Сессия закончилась, войдите снова'); }
  if (!res.ok) throw new Error((data && data.error) || `Ошибка ${res.status}`);
  return data;
}
const GET = (u) => api('GET', u);
const POST = (u, b) => api('POST', u, b || {});
const PATCH = (u, b) => api('PATCH', u, b || {});
async function loadMeta() { S.meta = await GET('/meta'); return S.meta; }

// ---------- уведомления и шторка ----------
let toastTimer;
function toast(msg, isError) {
  const el = $('#toast');
  el.innerHTML = `<div class="${isError ? 'err' : ''}">${esc(msg)}</div>`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.innerHTML = ''; }, isError ? 4500 : 2600);
}
function closeSheet() { $('#sheet-root').innerHTML = ''; document.body.style.overflow = ''; }
function sheet(title, html, mount) {
  const root = $('#sheet-root');
  root.innerHTML = `<div class="sheet-bg"><div class="sheet" role="dialog" aria-modal="true" aria-label="${esc(title)}">
    <div class="sheet-head"><h2>${esc(title)}</h2><button class="icon-btn" data-close aria-label="Закрыть">${icon('x')}</button></div>
    <div class="sheet-body">${html}</div></div></div>`;
  document.body.style.overflow = 'hidden';
  const bg = $('.sheet-bg', root);
  bg.addEventListener('mousedown', (e) => { if (e.target === bg) closeSheet(); });
  $('[data-close]', root).addEventListener('click', closeSheet);
  const body = $('.sheet-body', root);
  if (mount) mount(body);
  const first = $('input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select, textarea', body);
  if (first && window.matchMedia('(min-width: 900px)').matches) first.focus();
  return body;
}
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSheet(); });

const formObj = (form) => Object.fromEntries(new FormData(form).entries());
/** Отправка формы: блокирует кнопку, показывает ошибку сервера прямо в форме. */
function onSubmit(form, handler) {
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = $('button[type=submit]', form);
    const err = $('.form-error', form);
    if (err) err.classList.remove('on');
    if (btn) btn.disabled = true;
    try { await handler(formObj(form)); } catch (ex) {
      if (err) { err.textContent = ex.message; err.classList.add('on'); err.scrollIntoView({ block: 'nearest' }); } else toast(ex.message, true);
    } finally { if (btn) btn.disabled = false; }
  });
}
function confirmSheet(title, text, okLabel, fn, withReason) {
  sheet(title, `<form><p class="muted" style="margin-bottom:14px">${esc(text)}</p>
    ${withReason ? `<label class="field"><span>${esc(withReason)}</span><input type="text" name="reason" required maxlength="200"></label>` : ''}
    <div class="form-error"></div>
    <div class="btn-row fill"><button type="button" class="btn" data-no>Не сейчас</button><button type="submit" class="btn primary">${esc(okLabel)}</button></div></form>`,
  (body) => {
    $('[data-no]', body).addEventListener('click', closeSheet);
    onSubmit($('form', body), async (v) => { await fn(v); closeSheet(); });
  });
}
// ---------- навигация ----------
function navItems() {
  if (S.me.role === 'teacher') {
    return { main: [['/', 'Сегодня', 'home'], ['/groups', 'Группы', 'book'], ['/students', 'Ученики', 'users']], more: [], moreLabel: 'Профиль', moreIcon: 'user' };
  }
  const more = [['/applications', 'Заявки', 'inbox'], ['/families', 'Семьи', 'users'], ['/teachers', 'Учителя', 'user']];
  if (isOwner()) more.push(['/salaries', 'Зарплата учителей', 'coins'], ['/audit', 'Журнал действий', 'history'], ['/settings', 'Настройки школы', 'settings']);
  return { main: [['/', 'Главная', 'home'], ['/students', 'Ученики', 'users'], ['/groups', 'Группы', 'book'], ['/finance', 'Оплаты', 'wallet']], more, moreLabel: 'Ещё', moreIcon: 'more' };
}
const currentPath = () => (location.hash.replace(/^#/, '') || '/');
function go(path) { if (currentPath() === path) render(); else location.hash = path; }
function goBack(fallback) { if (S.navCount > 0) history.back(); else go(fallback || '/'); }
function sectionOf(path) {
  path = path.split('?')[0];
  if (path === '/') return '/';
  if (path.startsWith('/attendance')) return S.me.role === 'teacher' ? '/' : '/groups';
  if (/^\/families\/\d+\/pay$/.test(path)) return '/finance';
  const all = navItems().main.concat(navItems().more).map((i) => i[0]).filter((p) => p !== '/');
  return all.find((p) => path === p || path.startsWith(p + '/')) || '/more';
}

function renderShell() {
  const nav = navItems();
  const link = (i) => `<a href="#${i[0]}" data-nav="${i[0]}">${icon(i[2])}<span>${esc(i[1])}</span></a>`;
  $('#app').innerHTML = `
    <aside class="side">
      <div class="brand"><span style="display:flex;width:38px;height:38px;border-radius:11px;background:var(--accent);align-items:center;justify-content:center;flex:none"><svg width="22" height="22" viewBox="0 0 48 48" fill="none" stroke="#fff" stroke-width="3.4" stroke-linejoin="round"><rect x="13" y="13" width="22" height="22"/><rect x="13" y="13" width="22" height="22" transform="rotate(45 24 24)"/></svg></span><span>${esc(S.me.school_name)}</span></div>
      <nav>${nav.main.map(link).join('')}${nav.more.length ? '<div class="sep"></div>' + nav.more.map(link).join('') : ''}</nav>
      <div class="who"><b>${esc(S.me.name)}</b><span class="muted small">${ROLE[S.me.role]}</span>
        <button class="btn sm block" style="margin-top:12px" data-logout>${icon('logout')}Выйти</button></div>
    </aside>
    <div class="col">
      <header class="top"><button class="icon-btn back" id="top-back" aria-label="Назад" hidden>${icon('back')}</button><h1 id="top-title"></h1><div id="top-actions" class="btn-row"></div></header>
      <main id="view" tabindex="-1"></main>
    </div>
    <nav class="tabs" aria-label="Разделы">${nav.main.map(link).join('')}<a href="#/more" data-nav="/more">${icon(nav.moreIcon)}<span>${nav.moreLabel}</span></a></nav>`;
  $$('[data-logout]').forEach((b) => b.addEventListener('click', logout));
}
async function logout() {
  try { await POST('/logout'); } catch (e) { /* уже вышли */ }
  S.me = null; S.meta = null;
  location.hash = '/';
  renderLogin();
}

/** Заголовок страницы. opts: back — путь «назад», actions — html кнопок справа. */
function setTop(title, opts) {
  opts = opts || {};
  $('#top-title').textContent = title;
  document.title = `${title} — ${S.me.school_name}`;
  const back = $('#top-back');
  back.hidden = !opts.back;
  back.onclick = () => goBack(opts.back);
  $('#top-actions').innerHTML = opts.actions || '';
}
const view = () => $('#view');

const ROUTES = [];
function page(pattern, fn) { ROUTES.push([pattern.split('/'), fn]); }
function matchRoute(path) {
  const parts = path.split('?')[0].split('/');
  for (const [pat, fn] of ROUTES) {
    if (pat.length !== parts.length) continue;
    const params = {};
    if (pat.every((p, i) => (p[0] === ':' ? ((params[p.slice(1)] = decodeURIComponent(parts[i])), true) : p === parts[i]))) return [fn, params];
  }
  return null;
}
async function render() {
  if (!S.me) return renderLogin();
  if (!$('#view')) renderShell();
  closeSheet();
  const path = currentPath();
  const seq = ++S.seq;
  const sec = sectionOf(path);
  const inMore = navItems().more.some((i) => i[0] === sec);
  $$('[data-nav]').forEach((a) => a.classList.toggle('on', a.dataset.nav === sec || (inMore && a.dataset.nav === '/more' && !!a.closest('.tabs'))));
  const m = matchRoute(path);
  if (!m) { setTop('Страница не найдена', { back: '/' }); view().innerHTML = '<div class="card empty">Такой страницы нет.</div>'; return; }
  try {
    await m[0](m[1], () => seq === S.seq);
  } catch (e) {
    if (seq !== S.seq || !S.me) return;
    setTop('Не получилось', { back: '/' });
    view().innerHTML = `<div class="banner">${icon('alert')}<div><b>${esc(e.message)}</b><div class="small" style="margin-top:2px">Если это ошибка доступа — раздел закрыт для вашей роли.</div></div></div>`;
  }
  window.scrollTo(0, 0);
}
window.addEventListener('hashchange', () => { S.navCount += 1; render(); });

// ---------- вход ----------
async function renderLogin() {
  closeSheet();
  let info = { school_name: 'Школа Корана', demo: [] };
  try { info = await GET('/public'); } catch (e) { /* покажем форму без демо-кнопок */ }
  document.title = info.school_name;
  const roleIcon = { owner: 'star', admin: 'wallet', teacher: 'book' };
  $('#app').innerHTML = `<div class="login"><div class="login-card">
    <div class="mark">${LOGO}</div>
    <h1>${esc(info.school_name)}</h1>
    <p class="lead-text">Ученики, посещаемость, хифз и оплаты — в одном месте.</p>
    ${info.demo.length ? `<div class="sec-title"><h2>Быстрый демо-вход</h2></div>
    ${info.demo.map((d) => `<button class="card demo-btn" data-demo="${esc(d.login)}"><span class="lead">${icon(roleIcon[d.role])}</span><span class="main"><b>${esc(d.name.split(' ')[0])}</b><small>${esc(d.label)}</small></span>${icon('chev', 'chev muted')}</button>`).join('')}` : ''}
    <details ${info.demo.length ? '' : 'open'}><summary>Войти по логину и паролю</summary>
      <form class="card pad" style="margin-top:8px">
        <label class="field"><span>Логин</span><input type="text" name="login" autocomplete="username" autocapitalize="none" required></label>
        <label class="field"><span>Пароль</span><input type="password" name="password" autocomplete="current-password" required></label>
        <div class="form-error"></div>
        <button type="submit" class="btn primary block">Войти</button>
      </form></details>
  </div></div>`;
  const enter = async (me) => { S.me = me; S.navCount = 0; if (currentPath() !== '/') history.replaceState(null, '', '#/'); renderShell(); await render(); };
  $$('[data-demo]').forEach((b) => b.addEventListener('click', async () => {
    b.disabled = true;
    try { await enter(await POST('/demo-login', { login: b.dataset.demo })); } catch (e) { toast(e.message, true); b.disabled = false; }
  }));
  onSubmit($('.login form'), async (v) => enter(await POST('/login', v)));
}

async function boot() {
  try { S.me = await GET('/me'); } catch (e) { S.me = null; }
  if (S.me) { renderShell(); render(); } else renderLogin();
}
window.addEventListener('DOMContentLoaded', () => setTimeout(boot, 0));
