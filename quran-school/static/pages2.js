'use strict';
/* Страницы: оплаты, семьи, заявки, зарплата, учителя, настройки, журнал. */

const finTabs = (on) => `<div class="seg-tabs"><a href="#/finance" class="${on === 'debt' ? 'on' : ''}">Кто должен</a><a href="#/finance/payments" class="${on === 'pay' ? 'on' : ''}">Платежи</a></div>`;
const queryOf = () => new URLSearchParams((currentPath().split('?')[1]) || '');
const daysAgo = (ts) => { const n = Math.round((pd(S.me.today) - pd(ts)) / 86400000); return n <= 0 ? 'сегодня' : n === 1 ? 'вчера' : nWord(n, 'день', 'дня', 'дней') + ' назад'; };

// ---------- напоминание родителю ----------
async function openReminder(familyId) {
  let r;
  try { r = await POST('/finance/reminders', { family_id: familyId }); } catch (e) { return toast(e.message, true); }
  sheet('Напоминание родителю', `<p class="muted small" style="margin-bottom:10px">${esc(r.parent_name)} · ${esc(r.phone)} · к оплате ${money(r.due)}</p>
    <textarea id="rem-text" rows="13" aria-label="Текст напоминания">${esc(r.text)}</textarea>
    <p class="hint" style="margin-top:8px">Текст можно поправить. Приложение само ничего не отправляет — скопируйте и отправьте родителю.</p>
    <div class="btn-row fill"><button class="btn primary" id="rem-copy">${icon('copy')}Скопировать</button><button class="btn" id="rem-wa">${icon('msg')}WhatsApp</button></div>`, (body) => {
    $('#rem-copy', body).addEventListener('click', async () => {
      // Сначала способ, который работает и по обычному http в локальной сети, затем современный.
      const ta = $('#rem-text', body);
      ta.focus(); ta.select(); ta.setSelectionRange(0, ta.value.length);
      let ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      if (!ok && navigator.clipboard) { try { await navigator.clipboard.writeText(ta.value); ok = true; } catch (e) { ok = false; } }
      toast(ok ? 'Текст скопирован' : 'Текст выделен — скопируйте его вручную', !ok);
    });
    $('#rem-wa', body).addEventListener('click', () => {
      window.open(`https://wa.me/${r.phone.replace(/\D/g, '')}?text=${encodeURIComponent($('#rem-text', body).value)}`, '_blank', 'noopener');
    });
  });
}

// ---------- кто должен ----------
page('/finance', async (p, alive) => {
  const d = await GET('/finance/debtors');
  if (!alive()) return;
  setTop('Оплаты');
  view().innerHTML = `${finTabs('debt')}
    <div class="card totals" style="grid-template-columns:1fr 1fr"><div><div class="l">Всего должны</div><div class="v">${money(d.total)}</div></div>
      <div><div class="l">Из них за прошлые месяцы</div><div class="v" style="${d.overdue ? 'color:var(--warn)' : ''}">${money(d.overdue)}</div></div></div>
    <p class="muted small" style="margin:10px 2px 12px">${d.families.length ? `${nWord(d.families.length, 'семья', 'семьи', 'семей')} · срок оплаты за месяц — до ${d.due_day}-го числа` : ''}</p>
    <div class="stack">${d.families.map((f) => `<div class="card debtor">
        <div class="hd"><a href="#/families/${f.family_id}"><b>${esc(f.name)}</b></a><span class="sum">${money(f.due)}</span></div>
        <div class="muted small">${esc(f.parent_name)} · ${esc(f.parent_phone)}</div>
        <div class="small" style="margin-top:6px">${esc(f.children.join(', '))} · за ${esc(f.months.map((m) => m.split(' ')[0]).join(', '))}</div>
        <div class="badges" style="margin-top:8px">${f.overdue ? `<span class="badge warn">просрочено ${money(f.overdue)}</span>` : ''}<span class="badge">${f.last_reminder ? 'напоминали ' + daysAgo(f.last_reminder) : 'ещё не напоминали'}</span></div>
        <div class="btn-row fill"><button class="btn" data-rem="${f.family_id}">${icon('bell')}Напоминание</button><a class="btn primary" href="#/families/${f.family_id}/pay">Внести оплату</a></div>
      </div>`).join('') || `<div class="banner ok">${icon('check')}<div><b>Долгов нет</b><div class="small">Все семьи оплатили занятия.</div></div></div>`}</div>`;
  $$('[data-rem]').forEach((b) => b.addEventListener('click', () => openReminder(Number(b.dataset.rem))));
});

// ---------- платежи ----------
page('/finance/payments', async (p, alive) => {
  const month = queryOf().get('month') || '';
  const d = await GET('/finance/payments' + (month ? '?month=' + month : ''));
  if (!alive()) return;
  setTop('Оплаты');
  const jump = (m) => { history.replaceState(null, '', '#/finance/payments?month=' + m); render(); };
  view().innerHTML = `${finTabs('pay')}
    <div class="month-nav"><button class="icon-btn card" id="prev" aria-label="Предыдущий месяц">${icon('back')}</button><b>${esc(d.month_label)}</b>
      <button class="icon-btn card" id="next" aria-label="Следующий месяц" ${d.next ? '' : 'disabled style="opacity:.35"'}>${icon('chev')}</button></div>
    <div class="card totals"><div><div class="l">Поступило</div><div class="v">${money(d.total)}</div></div>
      <div><div class="l">Наличные</div><div class="v">${money(d.by_method.cash || 0)}</div></div>
      <div><div class="l">Перевод и карта</div><div class="v">${money((d.by_method.transfer || 0) + (d.by_method.card || 0))}</div></div></div>
    <section><div class="card list">${d.payments.map((x) => `<div class="row"><span class="main"><div class="t ${x.status === 'cancelled' ? 'struck' : ''}">${esc(x.student)}</div>
        <div class="s">${fmtD(x.paid_at)} · ${esc(x.group_name)} · за ${esc(x.month_label.split(' ')[0])} · ${METHOD[x.method] || esc(x.method)}</div>
        ${x.status === 'cancelled' ? `<div class="s">Отменён: ${esc(x.cancel_reason)}</div>` : ''}</span>
        <span class="side-r"><b class="num ${x.status === 'cancelled' ? 'struck' : ''}">${money(x.amount)}</b>${x.status === 'active' ? `<button class="btn sm" data-cancel="${x.id}" data-info="${esc(x.student)} — ${money(x.amount)}">Отменить</button>` : ''}</span></div>`).join('') || '<div class="empty">В этом месяце платежей не было</div>'}</div></section>`;
  $('#prev').addEventListener('click', () => jump(d.prev));
  $('#next').addEventListener('click', () => { if (d.next) jump(d.next); });
  $$('[data-cancel]').forEach((b) => b.addEventListener('click', () => confirmSheet('Отменить платёж?', `${b.dataset.info}. Платёж не удаляется — он останется в списке как отменённый, а долг вернётся.`, 'Отменить платёж', async (v) => { await POST(`/finance/payments/${b.dataset.cancel}/cancel`, v); toast('Платёж отменён'); render(); }, 'Причина отмены')));
});

// ---------- семьи ----------
page('/families', async (p, alive) => {
  const list = await GET('/families');
  if (!alive()) return;
  setTop('Семьи', { back: '/more' });
  view().innerHTML = `<div class="toolbar"><label class="search">${icon('search')}<input type="search" id="q" placeholder="Фамилия, родитель или телефон" aria-label="Поиск семьи"></label></div><div class="card list" id="list"></div>`;
  const draw = (ql) => {
    $('#list').innerHTML = list.filter((f) => !ql || (f.name + ' ' + f.parent_name + ' ' + f.parent_phone).toLowerCase().includes(ql)).map((f) => `<a class="row" href="#/families/${f.id}"><span class="main"><div class="t">${esc(f.name)}</div>
      <div class="s">${esc(f.parent_name)} · ${f.children.length ? esc(f.children.join(', ')) : 'нет учеников'}</div></span>${f.due ? `<span class="badge warn">долг ${money(f.due)}</span>` : ''}${chev()}</a>`).join('') || '<div class="empty">Ничего не найдено</div>';
  };
  draw('');
  $('#q').addEventListener('input', (e) => draw(e.target.value.trim().toLowerCase()));
});

page('/families/:id', async (p, alive) => {
  const f = await GET('/families/' + p.id);
  if (!alive()) return;
  setTop('Семья', { back: '/families' });
  view().innerHTML = `
    <div class="card profile"><h2>${esc(f.name)}</h2><div class="meta">${nWord(f.children.filter((c) => c.status === 'active').length, 'ученик', 'ученика', 'учеников')} в школе</div>
      <div class="kv"><span>${f.parent_gender === 'm' ? 'Отец' : 'Мать'} / плательщик</span><span>${esc(f.parent_name)}<br><a href="tel:${esc(f.parent_phone.replace(/[^+\d]/g, ''))}" style="color:var(--accent)">${esc(f.parent_phone)}</a></span></div>
      ${f.parent2_name ? `<div class="kv"><span>Второй родитель</span><span>${esc(f.parent2_name)}${f.parent2_phone ? '<br>' + esc(f.parent2_phone) : ''}</span></div>` : ''}
      ${f.note ? `<div class="kv"><span>Заметка</span><span>${esc(f.note)}</span></div>` : ''}
      <button class="btn sm" id="f-edit" style="margin-top:12px">${icon('edit')}Изменить контакты</button></div>
    <section><div class="card pad">
      <div class="stat"><b style="${f.due ? 'color:var(--warn)' : ''}">${money(f.due)}</b><span class="muted">${f.due ? 'к оплате' : '— долгов нет'}</span></div>
      ${f.last_reminder ? `<div class="muted small" style="margin-top:4px">Напоминали ${daysAgo(f.last_reminder.created_at)}${f.last_reminder.by_name ? ' · ' + esc(f.last_reminder.by_name.split(' ')[0]) : ''}</div>` : ''}
      ${f.due ? `<div class="btn-row fill" style="margin-top:12px"><button class="btn" id="f-rem">${icon('bell')}Напоминание</button><a class="btn primary" href="#/families/${f.id}/pay">Внести оплату</a></div>` : ''}</div></section>
    <section>${secTitle('Дети')}<div class="card list">${f.children.map((c) => `<a class="row" href="#/students/${c.id}"><span class="main"><div class="t">${esc(c.name)}</div><div class="s">${c.status === 'archived' ? 'в архиве' : esc(c.groups.join(', ') || 'без группы')}</div></span>${c.is_free ? '<span class="badge">бесплатно</span>' : ''}${chev()}</a>`).join('')}</div></section>
    <section>${secTitle('История оплат')}<div class="card list">${f.payments.map((x) => `<div class="row"><span class="main"><div class="t ${x.status === 'cancelled' ? 'struck' : ''}">${esc(x.first_name)} · ${esc(x.month_label)}</div>
      <div class="s">${fmtD(x.paid_at)} · ${esc(x.group_name)} · ${METHOD[x.method] || ''}${x.by_name ? ' · принял(а) ' + esc(x.by_name.split(' ')[0]) : ''}${x.status === 'cancelled' ? ' · отменён: ' + esc(x.cancel_reason) : ''}</div></span><b class="num ${x.status === 'cancelled' ? 'struck' : ''}">${money(x.amount)}</b></div>`).join('') || '<div class="empty">Оплат пока не было</div>'}</div></section>`;
  if ($('#f-rem')) $('#f-rem').addEventListener('click', () => openReminder(f.id));
  $('#f-edit').addEventListener('click', () => sheet('Контакты семьи', `<form>
    <label class="field"><span>Название семьи</span><input type="text" name="name" value="${esc(f.name)}" required></label>
    <div class="grid2"><label class="field"><span>Родитель / плательщик</span><input type="text" name="parent_name" value="${esc(f.parent_name)}" required></label>
      <label class="field"><span>Обращение</span><select name="parent_gender"><option value="f">уважаемая</option><option value="m" ${f.parent_gender === 'm' ? 'selected' : ''}>уважаемый</option></select></label></div>
    <label class="field"><span>Телефон</span><input type="tel" name="parent_phone" value="${esc(f.parent_phone)}" required></label>
    <div class="grid2"><label class="field"><span>Второй родитель</span><input type="text" name="parent2_name" value="${esc(f.parent2_name)}"></label>
      <label class="field"><span>Его телефон</span><input type="tel" name="parent2_phone" value="${esc(f.parent2_phone)}"></label></div>
    <label class="field"><span>Заметка</span><textarea name="note">${esc(f.note)}</textarea></label>
    <div class="form-error"></div><button type="submit" class="btn primary block">Сохранить</button></form>`, (body) => {
    onSubmit($('form', body), async (v) => { await PATCH('/families/' + f.id, v); closeSheet(); toast('Сохранено'); render(); });
  }));
});

// ---------- приём оплаты за семью ----------
page('/families/:id/pay', async (p, alive) => {
  const f = await GET('/families/' + p.id);
  if (!alive()) return;
  setTop('Приём оплаты', { back: '/families/' + p.id });
  const free = f.children.filter((c) => c.is_free && c.status === 'active');
  if (!f.open.length) {
    view().innerHTML = `<div class="banner ok">${icon('check')}<div><b>${esc(f.name)}: долгов нет</b><div class="small">Все начисления по текущий месяц оплачены.</div></div></div>
      <a class="btn block" style="margin-top:14px" href="#/families/${f.id}">К семье</a>`;
    return;
  }
  view().innerHTML = `
    <div style="margin:0 2px 12px"><b style="font-size:18px">${esc(f.name)}</b><div class="muted small">${esc(f.parent_name)} · ${esc(f.parent_phone)}</div></div>
    <form id="payform">
    <div class="card list">${f.open.map((c) => `<label class="pay-item"><input type="checkbox" data-c="${c.id}" checked aria-label="${esc(c.student)}, ${esc(c.month_label)}">
        <span class="main"><div class="t">${esc(c.student.split(' ')[0])} · <span style="text-transform:capitalize">${esc(c.month_label.split(' ')[0])}</span></div><div class="s">${esc(c.group_name)}</div>
        ${c.discount_pct ? `<div class="disc">${money(c.base)} − ${c.discount_pct}% · ${esc(c.discount_reason)}</div>` : ''}
        ${c.paid ? `<div class="s">уже внесено ${money(c.paid)} из ${money(c.amount)}</div>` : ''}</span>
        <input type="number" data-a="${c.id}" value="${c.due}" min="1" max="${c.due}" step="1" inputmode="numeric" aria-label="Сумма"></label>`).join('')}</div>
    ${free.length ? `<p class="hint" style="margin-top:10px">${esc(free.map((c) => c.first_name).join(', '))} — ${free.length > 1 ? 'учатся' : 'учится'} бесплатно, начислений нет.</p>` : ''}
    ${f.open.some((c) => c.discount_pct) ? `<p class="hint" style="margin-top:10px">Семейная скидка посчитана автоматически: второй ребёнок −${f.discounts.second}%, третий и далее −${f.discounts.third}%.</p>` : ''}
    <div class="field" style="margin-top:14px"><span>Способ оплаты</span><div class="methods">${Object.keys(METHOD).map((m, i) => `<label><input type="radio" name="method" value="${m}" ${i === 0 ? 'checked' : ''}><span>${METHOD[m][0].toUpperCase() + METHOD[m].slice(1)}</span></label>`).join('')}</div></div>
    <label class="field"><span>Дата оплаты</span><input type="date" name="paid_at" value="${S.me.today}" max="${S.me.today}" required></label>
    <div class="form-error"></div>
    <div class="foot-space"></div>
    <div class="foot"><div class="info"><b id="total"></b><span class="muted small" id="total-s"></span></div><button type="submit" class="btn primary lg" style="min-width:150px">Принять оплату</button></div>
    </form>`;
  const items = () => $$('[data-c]').filter((c) => c.checked).map((c) => ({ charge_id: Number(c.dataset.c), amount: Number($(`[data-a="${c.dataset.c}"]`).value) || 0 }));
  const recalc = () => {
    $$('[data-c]').forEach((c) => { $(`[data-a="${c.dataset.c}"]`).disabled = !c.checked; });
    const it = items();
    const sum = it.reduce((a, x) => a + x.amount, 0);
    $('#total').textContent = money(sum);
    $('#total-s').textContent = sum < f.due ? `останется ${money(f.due - sum)}` : 'долг будет закрыт полностью';
  };
  recalc();
  $$('[data-c], [data-a]').forEach((el) => el.addEventListener('input', recalc));
  onSubmit($('#payform'), async (v) => {
    const r = await POST('/finance/payments', { family_id: f.id, items: items(), method: v.method, paid_at: v.paid_at });
    toast(`Принято ${money(r.total)}${r.left ? ' · остаток ' + money(r.left) : ' · долг закрыт'}`);
    go('/families/' + f.id);
  });
});

// ---------- заявки ----------
const STAGE = { new: 'Новая', contacted: 'Связались', trial: 'Пробный урок', enrolled: 'Зачислен', declined: 'Отказ' };
const STAGE_TONE = { new: 'warn', contacted: '', trial: '', enrolled: 'ok', declined: '' };
let appFilter = 'open';

page('/applications', async (p, alive) => {
  const list = await GET('/applications');
  if (!alive()) return;
  setTop('Заявки', { back: '/more', actions: `<button class="btn primary sm" id="add">${icon('plus')}Заявка</button>` });
  const count = (k) => list.filter((a) => (k === 'open' ? ['new', 'contacted', 'trial'].includes(a.stage) : a.stage === k)).length;
  const draw = () => {
    const rows = list.filter((a) => (appFilter === 'open' ? ['new', 'contacted', 'trial'].includes(a.stage) : a.stage === appFilter));
    view().innerHTML = `<div class="chips">${[['open', 'В работе']].concat(Object.entries(STAGE)).map(([k, l]) => `<button class="chip ${appFilter === k ? 'on' : ''}" data-f="${k}">${l}<i>${count(k)}</i></button>`).join('')}</div>
      <div class="stack">${rows.map((a) => `<div class="card debtor">
        <div class="hd"><b>${esc(a.name)}</b><span class="badge ${STAGE_TONE[a.stage]}">${STAGE[a.stage]}</span></div>
        <div class="small" style="margin-top:2px">${genderWord(a.gender, a.age)}${a.age != null ? ', ' + ageText(a.age) : ''}${a.direction ? ' · ' + esc(a.direction) : ''}</div>
        <div class="muted small" style="margin-top:4px">${esc(a.parent_name)} · <a href="tel:${esc(a.phone.replace(/[^+\d]/g, ''))}" style="color:var(--accent)">${esc(a.phone)}</a></div>
        ${a.note ? `<div class="small" style="margin-top:6px">${esc(a.note)}</div>` : ''}
        <div class="muted small" style="margin-top:6px">Поступила ${fmtD(a.created_at)}${a.source ? ' · ' + esc(a.source) : ''}</div>
        <div class="btn-row" style="margin-top:12px">
          ${a.stage === 'new' ? `<button class="btn sm" data-stage="contacted" data-id="${a.id}">Связались</button>` : ''}
          ${a.stage === 'contacted' ? `<button class="btn sm" data-stage="trial" data-id="${a.id}">Пробный урок</button>` : ''}
          ${['new', 'contacted', 'trial'].includes(a.stage) ? `<button class="btn primary sm" data-enroll="${a.id}">Зачислить</button><button class="btn sm danger" data-stage="declined" data-id="${a.id}">Отказ</button>` : ''}
          ${a.stage === 'enrolled' && a.student_id ? `<a class="btn sm" href="#/students/${a.student_id}">Открыть ученика</a>` : ''}
          ${a.stage === 'declined' ? `<button class="btn sm" data-stage="new" data-id="${a.id}">Вернуть в работу</button>` : ''}
        </div></div>`).join('') || '<div class="card empty">Заявок на этом этапе нет</div>'}</div>`;
    $$('[data-f]').forEach((b) => b.addEventListener('click', () => { appFilter = b.dataset.f; draw(); }));
    $$('[data-stage]').forEach((b) => b.addEventListener('click', async () => {
      try { await PATCH('/applications/' + b.dataset.id, { stage: b.dataset.stage }); toast('Этап: ' + STAGE[b.dataset.stage]); render(); } catch (e) { toast(e.message, true); }
    }));
    $$('[data-enroll]').forEach((b) => b.addEventListener('click', () => enrollSheet(list.find((a) => String(a.id) === b.dataset.enroll))));
  };
  draw();
  $('#add').addEventListener('click', applicationForm);
});

async function enrollSheet(a) {
  const meta = await loadMeta();
  const best = meta.groups.find((g) => g.gender === a.gender && g.direction_id === a.direction_id && g.students < g.capacity);
  sheet('Зачисление', `<form><p style="margin-bottom:12px"><b>${esc(a.name)}</b><br><span class="muted small">${genderWord(a.gender, a.age)}${a.age != null ? ', ' + ageText(a.age) : ''}${a.direction ? ' · хочет на «' + esc(a.direction) + '»' : ''}</span></p>
    <label class="field"><span>Группа</span><select name="group_id" required>${groupOptions(meta.groups, best ? best.id : '', 'Выберите группу')}</select></label>
    <div class="form-error"></div>
    <button type="submit" class="btn primary block">Зачислить в группу</button>
    <p class="hint" style="margin-top:12px">Появятся карточка ученика и семьи. Если родитель с этим телефоном уже есть в базе, ребёнок попадёт в его семью, и скидка посчитается сама.</p></form>`, (body) => {
    onSubmit($('form', body), async (v) => {
      const r = await POST(`/applications/${a.id}/enroll`, { group_id: v.group_id });
      closeSheet(); S.meta = null; toast('Ученик зачислен'); go('/students/' + r.student_id);
    });
  });
}

async function applicationForm() {
  const meta = await loadMeta();
  sheet('Новая заявка', `<form>
    <div class="grid2"><label class="field"><span>Имя ребёнка</span><input type="text" name="child_first" required></label>
      <label class="field"><span>Фамилия</span><input type="text" name="child_last" required></label></div>
    <div class="grid2"><label class="field"><span>Пол</span><select name="gender"><option value="m">Мальчик</option><option value="f">Девочка</option></select></label>
      <label class="field"><span>Дата рождения</span><input type="date" name="birth_date" max="${S.me.today}"></label></div>
    <div class="grid2"><label class="field"><span>Родитель</span><input type="text" name="parent_name" required></label>
      <label class="field"><span>Обращение</span><select name="parent_gender"><option value="f">уважаемая</option><option value="m">уважаемый</option></select></label></div>
    <label class="field"><span>Телефон</span><input type="tel" name="phone" placeholder="+7 …" required></label>
    <div class="grid2"><label class="field"><span>Направление</span><select name="direction_id">${meta.directions.map((d) => `<option value="${d.id}">${esc(d.name)}</option>`).join('')}</select></label>
      <label class="field"><span>Откуда узнали</span><input type="text" name="source"></label></div>
    <label class="field"><span>Заметка</span><textarea name="note"></textarea></label>
    <div class="form-error"></div><button type="submit" class="btn primary block">Сохранить заявку</button></form>`, (body) => {
    onSubmit($('form', body), async (v) => { await POST('/applications', v); closeSheet(); appFilter = 'open'; toast('Заявка добавлена'); render(); });
  });
}

// ---------- зарплата учителей ----------
page('/salaries', async (p, alive) => {
  const month = queryOf().get('month') || '';
  const d = await GET('/salaries' + (month ? '?month=' + month : ''));
  if (!alive()) return;
  setTop('Зарплата учителей', { back: '/more' });
  const jump = (m) => { history.replaceState(null, '', '#/salaries?month=' + m); render(); };
  view().innerHTML = `
    <div class="month-nav"><button class="icon-btn card" id="prev" aria-label="Предыдущий месяц">${icon('back')}</button><b>${esc(d.month_label)}</b>
      <button class="icon-btn card" id="next" aria-label="Следующий месяц" ${d.next ? '' : 'disabled style="opacity:.35"'}>${icon('chev')}</button></div>
    <div class="card totals"><div><div class="l">Начислено</div><div class="v">${money(d.accrued)}</div></div>
      <div><div class="l">Выплачено</div><div class="v">${money(d.paid)}</div></div>
      <div><div class="l">Должен</div><div class="v" style="${d.due > 0 ? 'color:var(--warn)' : ''}">${money(d.due)}</div></div></div>
    ${d.is_current ? '<p class="muted small" style="margin:10px 2px 0">Месяц ещё идёт: суммы растут с каждым проведённым уроком и поступившей оплатой.</p>' : ''}
    <section class="stack">${d.teachers.map((t) => `<div class="card debtor">
      <div class="hd"><b>${esc(t.name)}</b><span class="sum" style="${t.due > 0 ? '' : 'color:var(--accent)'}">${t.due > 0 ? money(t.due) : 'выплачено'}</span></div>
      <div class="muted small">${t.pay_type === 'per_lesson' ? `${nWord(t.lessons, 'урок', 'урока', 'уроков')} × ${money(t.pay_value)}` : `${t.pay_value}% от оплат ${money(t.collected)}`} = ${money(t.accrued)}</div>
      ${t.payouts.map((x) => `<div class="kv small" style="margin-top:6px"><span>Выплата ${fmtD(x.paid_at)}</span><span class="num">${money(x.amount)} <button class="btn sm" data-undo="${x.id}" data-info="${esc(t.name)} — ${money(x.amount)}" style="margin-left:6px;min-height:30px">отменить</button></span></div>`).join('')}
      ${t.due > 0 ? `<button class="btn primary block" style="margin-top:12px" data-pay="${t.teacher_id}" data-due="${t.due}" data-name="${esc(t.name)}">Отметить выплату</button>` : ''}
    </div>`).join('') || '<div class="card empty">Нет данных за этот месяц</div>'}</section>`;
  $('#prev').addEventListener('click', () => jump(d.prev));
  $('#next').addEventListener('click', () => { if (d.next) jump(d.next); });
  $$('[data-pay]').forEach((b) => b.addEventListener('click', () => sheet('Выплата учителю', `<form><p class="muted" style="margin-bottom:12px">${esc(b.dataset.name)} · ${esc(d.month_label)} · к выплате ${money(b.dataset.due)}</p>
      <label class="field"><span>Сумма, ${esc(S.me.currency)}</span><input type="number" name="amount" value="${b.dataset.due}" min="1" max="${b.dataset.due}" inputmode="numeric" required></label>
      <label class="field"><span>Заметка</span><input type="text" name="note" placeholder="необязательно"></label>
      <div class="form-error"></div><button type="submit" class="btn primary block">Выплачено</button></form>`, (body) => {
    onSubmit($('form', body), async (v) => { await POST('/salaries/payouts', { teacher_id: Number(b.dataset.pay), month: d.month, amount: Number(v.amount), note: v.note }); closeSheet(); toast('Выплата записана'); render(); });
  })));
  $$('[data-undo]').forEach((b) => b.addEventListener('click', () => confirmSheet('Отменить выплату?', `${b.dataset.info}. Запись останется в журнале как отменённая.`, 'Отменить выплату', async () => { await POST(`/salaries/payouts/${b.dataset.undo}/cancel`); toast('Выплата отменена'); render(); })));
});

// ---------- учителя ----------
page('/teachers', async (p, alive) => {
  const list = await GET('/teachers');
  if (!alive()) return;
  setTop('Учителя', { back: '/more', actions: isOwner() ? `<button class="btn primary sm" id="add">${icon('plus')}Учитель</button>` : '' });
  view().innerHTML = `<div class="stack">${list.map((t) => `<div class="card debtor">
    <div class="hd"><b>${esc(t.name)}</b>${t.status === 'archived' ? '<span class="badge">в архиве</span>' : `<span class="badge">${nWord(t.students, 'ученик', 'ученика', 'учеников')}</span>`}</div>
    <div class="muted small">${esc(t.phone)}${t.login ? ' · вход: ' + esc(t.login) : ' · входа в систему нет'}</div>
    <div class="small" style="margin-top:6px">${esc(t.groups.join(' · ') || 'нет действующих групп')}</div>
    ${isOwner() ? `<div class="small muted" style="margin-top:6px">Оплата: ${t.pay_type === 'per_lesson' ? money(t.pay_value) + ' за проведённый урок' : t.pay_value + '% от оплат его групп'}</div>
    <div class="btn-row" style="margin-top:12px"><button class="btn sm" data-edit="${t.id}">${icon('edit')}Изменить</button>
      ${t.status === 'active' ? `<button class="btn sm danger" data-arch="${t.id}" data-name="${esc(t.name)}">В архив</button>` : `<button class="btn sm" data-rest="${t.id}">Вернуть</button>`}</div>` : ''}
  </div>`).join('')}</div>`;
  if (!isOwner()) return;
  const form = (t) => sheet(t ? 'Данные учителя' : 'Новый учитель', `<form>
    <label class="field"><span>Имя и фамилия</span><input type="text" name="name" value="${esc(t ? t.name : '')}" required></label>
    <div class="grid2"><label class="field"><span>Пол</span><select name="gender"><option value="m">Мужчина</option><option value="f" ${t && t.gender === 'f' ? 'selected' : ''}>Женщина</option></select></label>
      <label class="field"><span>Телефон</span><input type="tel" name="phone" value="${esc(t ? t.phone : '')}"></label></div>
    <div class="grid2"><label class="field"><span>Схема оплаты</span><select name="pay_type"><option value="per_lesson">За урок</option><option value="percent" ${t && t.pay_type === 'percent' ? 'selected' : ''}>% от оплат</option></select></label>
      <label class="field"><span>Ставка</span><input type="number" name="pay_value" min="0" inputmode="numeric" value="${t ? t.pay_value : 900}" required></label></div>
    ${t ? '' : `<p class="hint" style="margin-top:4px">Чтобы учитель мог входить с телефона, задайте логин и пароль (можно позже).</p>
    <div class="grid2"><label class="field"><span>Логин</span><input type="text" name="login" autocapitalize="none" autocomplete="off"></label>
      <label class="field"><span>Пароль</span><input type="text" name="password" autocomplete="off"></label></div>`}
    <div class="form-error"></div><button type="submit" class="btn primary block">${t ? 'Сохранить' : 'Добавить учителя'}</button></form>`, (body) => {
    onSubmit($('form', body), async (v) => { if (t) await PATCH('/teachers/' + t.id, v); else await POST('/teachers', v); closeSheet(); S.meta = null; toast('Сохранено'); render(); });
  });
  $('#add').addEventListener('click', () => form(null));
  $$('[data-edit]').forEach((b) => b.addEventListener('click', () => form(list.find((t) => String(t.id) === b.dataset.edit))));
  $$('[data-arch]').forEach((b) => b.addEventListener('click', () => confirmSheet('Учителя в архив?', `${b.dataset.name} больше не сможет входить в систему. История уроков и выплат сохранится.`, 'В архив', async () => { await PATCH('/teachers/' + b.dataset.arch, { status: 'archived' }); S.meta = null; toast('Учитель в архиве'); render(); })));
  $$('[data-rest]').forEach((b) => b.addEventListener('click', async () => { try { await PATCH('/teachers/' + b.dataset.rest, { status: 'active' }); S.meta = null; toast('Учитель возвращён'); render(); } catch (e) { toast(e.message, true); } }));
});

// ---------- настройки, журнал, «ещё» ----------
page('/settings', async (p, alive) => {
  const s = await GET('/settings');
  if (!alive()) return;
  setTop('Настройки школы', { back: '/more' });
  view().innerHTML = `<form class="card pad">
    <label class="field"><span>Название школы</span><input type="text" name="school_name" value="${esc(s.school_name)}" required></label>
    <div class="grid2"><label class="field"><span>Валюта</span><input type="text" name="currency" value="${esc(s.currency)}" maxlength="5" required></label>
      <label class="field"><span>Оплата до числа</span><input type="number" name="due_day" min="1" max="28" value="${esc(s.due_day)}" inputmode="numeric" required></label></div>
    <div class="grid2"><label class="field"><span>Скидка второму ребёнку, %</span><input type="number" name="discount2" min="0" max="100" value="${esc(s.discount2)}" inputmode="numeric" required></label>
      <label class="field"><span>Третьему и далее, %</span><input type="number" name="discount3" min="0" max="100" value="${esc(s.discount3)}" inputmode="numeric" required></label></div>
    <p class="hint">Новые скидки применяются к следующим начислениям. Уже выставленные суммы не меняются.</p>
    <div class="form-error"></div><button type="submit" class="btn primary block">Сохранить</button></form>`;
  onSubmit($('form', view()), async (v) => { await PATCH('/settings', v); S.me = await GET('/me'); renderShell(); toast('Настройки сохранены'); render(); });
});

page('/audit', async (p, alive) => {
  const list = await GET('/audit');
  if (!alive()) return;
  setTop('Журнал действий', { back: '/more' });
  view().innerHTML = `<p class="muted small" style="margin:0 2px 10px">Кто и что менял. Записи не удаляются.</p><div class="card list">${list.map((a) => `<div class="row"><span class="main"><div class="t">${esc(a.action)}</div><div class="s">${esc(a.details)}</div></span>
    <span class="side-r small muted"><span>${esc((a.user_name || '').split(' ')[0])}</span><span class="num">${fmtD(a.at)} ${esc(a.at.slice(11, 16))}</span></span></div>`).join('')}</div>`;
});

page('/more', async () => {
  const nav = navItems();
  setTop(nav.moreLabel);
  view().innerHTML = `<div class="card profile"><h2>${esc(S.me.name)}</h2><div class="meta" style="margin-bottom:0">${ROLE[S.me.role]} · ${esc(S.me.school_name)}</div></div>
    ${nav.more.length ? `<section><div class="card list">${nav.more.map((i) => `<a class="row" href="#${i[0]}"><span class="lead">${icon(i[2])}</span><span class="main"><div class="t">${esc(i[1])}</div></span>${chev()}</a>`).join('')}</div></section>` : ''}
    <section><button class="btn block" data-logout2>${icon('logout')}Выйти</button></section>`;
  $('[data-logout2]').addEventListener('click', logout);
});
