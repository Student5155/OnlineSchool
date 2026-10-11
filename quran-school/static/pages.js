'use strict';
/* Страницы: главная, ученики, хифз, группы, посещаемость. */

const chev = () => icon('chev', 'chev');
const streakText = (n) => `${nWord(n, 'пропуск', 'пропуска', 'пропусков')} подряд`;
const genderWord = (g, age) => (age != null && age >= 18 ? (g === 'f' ? 'женщина' : 'мужчина') : g === 'f' ? 'девочка' : 'мальчик');
const secTitle = (t, link) => `<div class="sec-title"><h2>${esc(t)}</h2>${link || ''}</div>`;
const pctText = (v) => (v == null ? '—' : v + '%');
const hifzShort = (h) => (h.juz_count ? nWord(h.juz_count, 'джуз', 'джуза', 'джузов') : h.surahs ? nWord(h.surahs, 'сура', 'суры', 'сур') : '');
const groupOptions = (groups, selected, placeholder) => `${placeholder ? `<option value="">${esc(placeholder)}</option>` : ''}${groups.map((g) => `<option value="${g.id}" ${String(selected) === String(g.id) ? 'selected' : ''}>${esc(g.name)} · ${genderGroup(g.gender)} · ${g.students}/${g.capacity}</option>`).join('')}`;

// ---------- главная ----------
page('/', async (p, alive) => {
  const d = await GET('/dashboard');
  if (!alive()) return;
  if (S.me.role === 'teacher') homeTeacher(d); else homeStaff(d);
});

function attentionRow(href, ic, tone, title, sub) {
  return `<a class="row" href="#${href}"><span class="lead ${tone}">${icon(ic)}</span><span class="main"><div class="t">${title}</div><div class="s">${sub}</div></span>${chev()}</a>`;
}
function absentRows(list) {
  return list.map((a) => attentionRow(`/students/${a.student_id}`, 'alert', 'danger', `${esc(a.name)} — ${nWord(a.count, 'пропуск', 'пропуска', 'пропусков')} подряд`,
    `${esc(a.group_name)} · ${a.dates.slice().reverse().map(fmtD).join(', ')}`));
}
function unmarkedRows(list) {
  return list.map((u) => attentionRow(`/attendance/${u.group_id}/${u.date}`, 'calendar', 'warn', 'Не отмечена посещаемость',
    `${esc(u.group)} · ${fmtD(u.date)}${S.me.role === 'teacher' ? '' : ' · ' + esc(u.teacher)}`));
}

function homeStaff(d) {
  setTop('Главная');
  const f = d.finance;
  const pct = f.expected ? Math.round((f.collected * 100) / f.expected) : 0;
  const att = d.attendance;
  const delta = att.week != null && att.prev_week != null ? att.week - att.prev_week : null;
  const attn = absentRows(d.absent3);
  if (d.applications_new) attn.push(attentionRow('/applications', 'inbox', '', `${nWord(d.applications_new, 'новая заявка', 'новые заявки', 'новых заявок')}`, 'Ждут первого звонка родителям'));
  if (f.debt_overdue) attn.push(attentionRow('/finance', 'wallet', 'warn', `Долг за прошлые месяцы — ${money(f.debt_overdue)}`, 'Откройте «Кто должен», чтобы отправить напоминание'));
  attn.push(...unmarkedRows(d.unmarked));
  if (d.salary_due != null && d.salary_due > 0) attn.push(attentionRow('/salaries', 'coins', '', `Учителям к выплате — ${money(d.salary_due)}`, 'Начислено и ещё не выплачено'));
  const lessons = d.lessons.map((l) => `<a class="row" href="#/attendance/${l.group_id}/${d.today}"><span class="lead time">${esc(l.time)}</span>
      <span class="main"><div class="t">${esc(l.group)}</div><div class="s">${esc(l.teacher)}${l.room ? ' · ' + esc(l.room) : ''}</div></span>
      ${l.marked ? `<span class="badge ok">${icon('check')}${l.present} из ${l.total}</span>` : '<span class="badge">не отмечено</span>'}</a>`).join('');
  view().innerHTML = `
    <div class="hello"><b>Ассаляму алейкум, ${esc(S.me.name.split(' ')[0])}!</b><span class="muted">${fmtDL(d.today)}</span></div>
    <div class="kpis">
      <a class="card kpi" href="#/students"><span class="l">Учеников</span><span class="v">${d.students}</span>
        <span class="s">${d.students_new ? '+' + d.students_new + ' в этом месяце' : 'без новых в этом месяце'}${d.students_left ? ', ушло ' + d.students_left : ''} · ${nWord(d.groups, 'группа', 'группы', 'групп')}</span></a>
      <a class="card kpi" href="#/finance/payments"><span class="l">Собрано за ${esc(d.month_label.split(' ')[0])}</span><span class="v">${money(f.collected)}</span>
        <span class="bar"><i style="width:${Math.min(pct, 100)}%"></i></span><span class="s">${pct}% из ${money(f.expected)}</span></a>
      <a class="card kpi ${f.debt ? 'warn' : ''}" href="#/finance"><span class="l">Долг</span><span class="v">${money(f.debt)}</span>
        <span class="s">${f.debt ? nWord(f.debt_families, 'семья', 'семьи', 'семей') + (f.debt_overdue ? ' · ' + money(f.debt_overdue) + ' за прошлые месяцы' : '') : 'все оплатили'}</span></a>
      <div class="card kpi"><span class="l">Посещаемость за 7 дней</span><span class="v">${pctText(att.week)}</span>
        <span class="s">${delta == null ? 'нет данных за прошлую неделю' : delta === 0 ? 'как на прошлой неделе' : (delta > 0 ? 'выше' : 'ниже') + ' прошлой недели на ' + Math.abs(delta) + ' п. п.'}</span></div>
    </div>
    <section>${secTitle('Требует внимания')}
      <div class="card list">${attn.join('') || `<div class="row"><span class="lead">${icon('check')}</span><span class="main"><div class="t">Всё спокойно</div><div class="s">Пропусков подряд, долгов и новых заявок нет</div></span></div>`}</div></section>
    <section>${secTitle('Уроки сегодня')}
      <div class="card list">${lessons || '<div class="empty">Сегодня уроков нет</div>'}</div></section>
    <section>${secTitle('Оплаты за три месяца', '<a href="#/finance/payments">Все платежи</a>')}
      <div class="card months">${f.months.map((m) => { const p2 = m.expected ? Math.round((m.collected * 100) / m.expected) : 0; return `<div class="month-row"><div class="hd"><b>${esc(m.label)}</b><span class="num">${money(m.collected)} <span class="muted">из ${money(m.expected)} · ${p2}%</span></span></div><div class="bar"><i style="width:${Math.min(p2, 100)}%"></i></div></div>`; }).join('')}</div></section>`;
}

function homeTeacher(d) {
  setTop('Сегодня');
  const lessons = d.lessons.map((l) => `<div class="card lesson"><div class="hd"><span class="time">${esc(l.time)}</span><span class="name">${esc(l.group)}</span></div>
      <div class="muted small">${nWord(l.total, 'ученик', 'ученика', 'учеников')}${l.room ? ' · ' + esc(l.room) : ''}</div>
      ${l.marked ? `<a class="btn block" href="#/attendance/${l.group_id}/${d.today}">${icon('check')}Отмечено: ${l.present} из ${l.total} · изменить</a>`
    : `<a class="btn primary lg block" href="#/attendance/${l.group_id}/${d.today}">Отметить посещаемость</a>`}</div>`).join('');
  const attn = absentRows(d.absent3).concat(unmarkedRows(d.unmarked));
  view().innerHTML = `
    <div class="hello"><b>Ассаляму алейкум, ${esc(S.me.name.split(' ')[0])}!</b><span class="muted">${fmtDL(d.today)}</span></div>
    <div class="stack">${lessons || '<div class="card empty">Сегодня у вас уроков нет</div>'}</div>
    ${attn.length ? `<section>${secTitle('Обратите внимание')}<div class="card list">${attn.join('')}</div></section>` : ''}
    <section>${secTitle('Мои группы')}
      <div class="card list">${d.groups.map((g) => `<a class="row" href="#/groups/${g.id}"><span class="lead">${icon('book')}</span><span class="main"><div class="t">${esc(g.name)}</div><div class="s">${esc(schedText(g.schedule))} · ${nWord(g.students, 'ученик', 'ученика', 'учеников')}</div></span>${chev()}</a>`).join('')}</div></section>
    <section><div class="card kpi"><span class="l">Посещаемость моих групп за 7 дней</span><span class="v">${pctText(d.attendance.week)}</span></div></section>`;
}

// ---------- ученики ----------
const FILTER = { q: '', group: '', status: 'active' };

function studentBadges(s) {
  const b = [];
  if (s.absent_streak >= 3) b.push(`<span class="badge danger">${streakText(s.absent_streak)}</span>`);
  if (s.debt) b.push(`<span class="badge warn">долг ${money(s.debt)}</span>`);
  if (s.is_free) b.push('<span class="badge">бесплатно</span>');
  return b.join('');
}

page('/students', async (p, alive) => {
  if (!isStaff()) FILTER.status = 'active';
  const [list] = await Promise.all([GET('/students?status=' + FILTER.status), S.meta ? null : loadMeta()]);
  if (!alive()) return;
  setTop('Ученики', { actions: isStaff() ? `<button class="btn primary sm" id="add">${icon('plus')}Ученик</button>` : '' });
  view().innerHTML = `
    <div class="toolbar"><label class="search">${icon('search')}<input type="search" id="q" placeholder="Имя или фамилия" value="${esc(FILTER.q)}" aria-label="Поиск ученика"></label></div>
    <div class="toolbar"><select id="grp" aria-label="Группа"><option value="">Все группы</option>${S.meta.groups.map((g) => `<option value="${g.id}" ${FILTER.group === String(g.id) ? 'selected' : ''}>${esc(g.name)}</option>`).join('')}</select>
      ${isStaff() ? `<select id="st" aria-label="Статус" style="max-width:150px"><option value="active">Учатся</option><option value="archived" ${FILTER.status === 'archived' ? 'selected' : ''}>В архиве</option></select>` : ''}</div>
    <div class="muted small" id="count" style="margin:0 2px 8px"></div>
    <div class="card list" id="list"></div>`;
  const draw = () => {
    const ql = FILTER.q.trim().toLowerCase();
    const rows = list.filter((s) => (!ql || s.name.toLowerCase().includes(ql)) && (!FILTER.group || s.groups.some((g) => String(g.id) === FILTER.group)));
    $('#count').textContent = rows.length === list.length ? `Всего: ${list.length}` : `Найдено: ${rows.length} из ${list.length}`;
    $('#list').innerHTML = rows.map((s) => `<a class="row" href="#/students/${s.id}"><span class="main"><div class="t">${esc(s.name)}</div>
        <div class="s">${s.status === 'archived' ? 'в архиве' + (s.archive_reason ? ' · ' + esc(s.archive_reason) : '') : esc(s.groups.map((g) => g.name).join(', ') || 'без группы')}${s.age != null ? ' · ' + ageText(s.age) : ''}</div>
        <div class="badges" style="margin-top:${studentBadges(s) ? 5 : 0}px">${studentBadges(s)}</div></span>
        <span class="side-r"><span class="small muted num">${s.attendance != null ? 'посещ. ' + s.attendance + '%' : ''}</span><span class="small muted">${hifzShort(s.hifz)}</span></span>${chev()}</a>`).join('')
      || '<div class="empty">Никого не найдено</div>';
  };
  draw();
  $('#q').addEventListener('input', (e) => { FILTER.q = e.target.value; draw(); });
  $('#grp').addEventListener('change', (e) => { FILTER.group = e.target.value; draw(); });
  if ($('#st')) $('#st').addEventListener('change', (e) => { FILTER.status = e.target.value; render(); });
  if ($('#add')) $('#add').addEventListener('click', studentForm);
});

async function studentForm() {
  const [meta, families] = await Promise.all([loadMeta(), GET('/families')]);
  sheet('Новый ученик', `<form>
    <div class="grid2"><label class="field"><span>Имя</span><input type="text" name="first_name" required></label>
      <label class="field"><span>Фамилия</span><input type="text" name="last_name" required></label></div>
    <div class="grid2"><label class="field"><span>Пол</span><select name="gender"><option value="m">Мальчик</option><option value="f">Девочка</option></select></label>
      <label class="field"><span>Дата рождения</span><input type="date" name="birth_date" max="${S.me.today}"></label></div>
    <label class="field"><span>Семья</span><select name="family_id"><option value="">Новая семья</option>${families.map((f) => `<option value="${f.id}">${esc(f.name)} · ${esc(f.parent_name)}</option>`).join('')}</select></label>
    <div id="newfam"><label class="field"><span>Имя родителя</span><input type="text" name="parent_name"></label>
      <label class="field"><span>Телефон родителя</span><input type="tel" name="parent_phone" placeholder="+7 …"></label></div>
    <label class="field"><span>Группа</span><select name="group_id">${groupOptions(meta.groups, '', 'Пока без группы')}</select></label>
    <p class="hint">Если в семье уже есть ученик, скидка второму ребёнку посчитается сама.</p>
    <div class="form-error"></div><button type="submit" class="btn primary block">Добавить ученика</button></form>`, (body) => {
    const fam = $('[name=family_id]', body);
    fam.addEventListener('change', () => { $('#newfam', body).hidden = !!fam.value; });
    onSubmit($('form', body), async (v) => {
      const r = await POST('/students', v);
      closeSheet(); toast('Ученик добавлен'); go('/students/' + r.id);
    });
  });
}

page('/students/:id', async (p, alive) => {
  const s = await GET('/students/' + p.id);
  if (!alive()) return;
  setTop('Ученик', { back: '/students' });
  const h = s.hifz;
  const att = s.attendance;
  const dot = (m) => `<span class="dot ${m.status}" title="${fmtD(m.date)} · ${esc(m.group_name)}">${m.status === 'present' ? icon('check') : m.status === 'late' ? icon('clock') : m.status === 'absent' ? icon('x') : 'У'}</span>`;
  const staff = isStaff();
  const charges = staff ? s.charges.map((c) => {
    const due = c.amount - c.paid;
    const state = c.discount_pct === 100 ? '<span class="badge">бесплатно</span>' : due <= 0 ? '<span class="badge ok">оплачено</span>' : `<span class="badge warn">долг ${money(due)}</span>`;
    return `<div class="row"><span class="main"><div class="t" style="text-transform:capitalize">${esc(c.month_label)}</div><div class="s">${esc(c.group_name)} · ${money(c.amount)}${c.discount_pct && c.discount_pct < 100 ? ` (−${c.discount_pct}%, ${esc(c.discount_reason)})` : ''}</div></span>${state}</div>`;
  }).join('') : '';
  view().innerHTML = `
    <div class="card profile"><h2>${esc(s.name)}</h2>
      <div class="meta">${genderWord(s.gender, s.age)}${s.age != null ? ', ' + ageText(s.age) : ''} · в школе с ${fmtD(s.joined_at)} ${pd(s.joined_at).getFullYear()}</div>
      <div class="badges">${s.status === 'archived' ? '<span class="badge">в архиве</span>' : ''}${s.groups.map((g) => `<a class="badge ok" href="#/groups/${g.id}">${esc(g.name)}</a>`).join('') || (s.status === 'active' ? '<span class="badge">без группы</span>' : '')}${s.is_free ? '<span class="badge">учится бесплатно</span>' : ''}</div>
      ${s.status === 'archived' ? `<p class="muted small" style="margin-top:10px">В архиве с ${fmtD(s.archived_at)}: ${esc(s.archive_reason)}</p>` : ''}
      ${s.is_free && s.free_reason ? `<p class="muted small" style="margin-top:8px">Причина: ${esc(s.free_reason)}</p>` : ''}
      ${s.note ? `<p class="small" style="margin-top:8px">${esc(s.note)}</p>` : ''}</div>
    ${att.absent_streak >= 3 ? `<div class="banner" style="margin-top:12px">${icon('alert')}<div><b>${nWord(att.absent_streak, 'пропуск', 'пропуска', 'пропусков')} подряд</b><div class="small">Стоит позвонить родителям и узнать, всё ли в порядке.</div></div></div>` : ''}
    <section>${secTitle('Хифз')}
      <div class="card pad"><div class="stat"><b>${h.pct}%</b><span class="muted">Корана · ${nWord(h.surahs, 'сура', 'суры', 'сур')}${h.juz_count ? ' · ' + nWord(h.juz_count, 'джуз', 'джуза', 'джузов') + ' целиком (' + h.juz_done.slice().reverse().join(', ') + ')' : ''}</span></div>
        <div class="bar" style="margin:10px 0 14px"><i style="width:${Math.max(h.pct, 0.5)}%"></i></div>
        <a class="btn ${s.status === 'active' ? 'primary' : ''} block" href="#/students/${s.id}/hifz">${icon('book')}${s.status === 'active' ? 'Отметить сданную суру' : 'Открыть прогресс'}</a></div></section>
    <section>${secTitle('Посещаемость')}
      <div class="card pad"><div class="stat"><b>${pctText(att.pct)}</b><span class="muted">за три месяца</span></div>
        ${att.marks.length ? `<div class="dots">${att.marks.slice().reverse().map(dot).join('')}</div><div class="muted small" style="margin-top:8px">Последние ${nWord(att.marks.length, 'урок', 'урока', 'уроков')}, слева направо — от старых к новым</div>` : '<div class="muted small" style="margin-top:6px">Отметок пока нет</div>'}</div></section>
    <section>${secTitle('Родители')}
      <div class="card list"><a class="row" href="tel:${esc(s.contact.phone.replace(/[^+\d]/g, ''))}"><span class="lead">${icon('phone')}</span><span class="main"><div class="t">${esc(s.contact.name)}</div><div class="s">${esc(s.contact.phone)}</div></span></a>
        ${staff ? `<a class="row" href="#/families/${s.family.id}"><span class="lead">${icon('users')}</span><span class="main"><div class="t">${esc(s.family.name)}</div><div class="s">Семья, оплаты и напоминания</div></span>${chev()}</a>` : ''}</div></section>
    ${staff ? `<section>${secTitle('Начисления', `<a href="#/families/${s.family.id}/pay">Внести оплату</a>`)}<div class="card list">${charges || '<div class="empty">Начислений пока нет</div>'}</div></section>
    <section>${secTitle('Действия')}<div class="card list">
      ${s.status === 'active' ? `<button class="row" id="a-enroll"><span class="lead">${icon('plus')}</span><span class="main"><div class="t">Записать в группу</div></span></button>
      ${s.groups.map((g) => `<button class="row" data-unenroll="${g.enrollment_id}" data-name="${esc(g.name)}"><span class="lead">${icon('x')}</span><span class="main"><div class="t">Убрать из группы</div><div class="s">${esc(g.name)}</div></span></button>`).join('')}` : ''}
      <button class="row" id="a-edit"><span class="lead">${icon('edit')}</span><span class="main"><div class="t">Изменить данные</div></span></button>
      ${isOwner() && s.status === 'active' ? `<button class="row" id="a-free"><span class="lead">${icon('star')}</span><span class="main"><div class="t">${s.is_free ? 'Отменить бесплатное обучение' : 'Назначить бесплатное обучение'}</div><div class="s">Действует на следующие начисления</div></span></button>` : ''}
      ${s.status === 'active' ? `<button class="row" id="a-archive"><span class="lead danger">${icon('archive')}</span><span class="main"><div class="t">Перевести в архив</div><div class="s">История посещений и оплат сохранится</div></span></button>`
    : `<button class="row" id="a-restore"><span class="lead">${icon('history')}</span><span class="main"><div class="t">Вернуть из архива</div></span></button>`}
    </div></section>` : ''}`;
  if (!staff) return;
  const on = (sel, fn) => { const el = $(sel); if (el) el.addEventListener('click', fn); };
  on('#a-enroll', async () => {
    const meta = await loadMeta();
    sheet('Записать в группу', `<form><p class="muted" style="margin-bottom:12px">${esc(s.name)}, ${genderWord(s.gender, s.age)}</p>
      <label class="field"><span>Группа</span><select name="group_id" required>${groupOptions(meta.groups, '', 'Выберите группу')}</select></label>
      <div class="form-error"></div><button type="submit" class="btn primary block">Записать</button></form>`, (body) => {
      onSubmit($('form', body), async (v) => { await POST('/enrollments', { student_id: s.id, group_id: v.group_id }); closeSheet(); toast('Записан в группу'); render(); });
    });
  });
  $$('[data-unenroll]').forEach((b) => b.addEventListener('click', () => confirmSheet('Убрать из группы?', `${s.name} перестанет числиться в группе «${b.dataset.name}». Прошлые отметки и оплаты сохранятся.`, 'Убрать', async () => { await POST(`/enrollments/${b.dataset.unenroll}/end`); toast('Убран из группы'); render(); })));
  on('#a-edit', () => sheet('Данные ученика', `<form>
      <div class="grid2"><label class="field"><span>Имя</span><input type="text" name="first_name" value="${esc(s.first_name)}" required></label>
        <label class="field"><span>Фамилия</span><input type="text" name="last_name" value="${esc(s.last_name)}" required></label></div>
      <label class="field"><span>Дата рождения</span><input type="date" name="birth_date" value="${esc(s.birth_date || '')}" max="${S.me.today}"></label>
      <label class="field"><span>Заметка</span><textarea name="note">${esc(s.note)}</textarea></label>
      <div class="form-error"></div><button type="submit" class="btn primary block">Сохранить</button></form>`, (body) => {
    onSubmit($('form', body), async (v) => { await PATCH('/students/' + s.id, v); closeSheet(); toast('Сохранено'); render(); });
  }));
  on('#a-free', () => {
    if (s.is_free) return confirmSheet('Отменить бесплатное обучение?', 'Со следующего начисления ученик будет платить как все.', 'Отменить', async () => { await PATCH('/students/' + s.id, { is_free: false }); toast('Сохранено'); render(); });
    confirmSheet('Бесплатное обучение', 'Следующие начисления этому ученику будут нулевыми.', 'Назначить', async (v) => { await PATCH('/students/' + s.id, { is_free: true, free_reason: v.reason }); toast('Сохранено'); render(); }, 'Причина');
  });
  on('#a-archive', () => confirmSheet('Перевести в архив?', `${s.name} будет убран из групп. Ничего не удаляется: посещения, хифз и оплаты останутся, ученика можно вернуть.`, 'В архив', async (v) => { await PATCH('/students/' + s.id, { status: 'archived', reason: v.reason }); toast('Ученик в архиве'); render(); }, 'Причина'));
  on('#a-restore', () => confirmSheet('Вернуть из архива?', 'После возвращения запишите ученика в группу.', 'Вернуть', async () => { await PATCH('/students/' + s.id, { status: 'active' }); toast('Ученик возвращён'); render(); }));
});

// ---------- хифз ----------
page('/students/:id/hifz', async (p, alive) => {
  let d = await GET(`/students/${p.id}/hifz`);
  if (!alive()) return;
  setTop('Хифз', { back: '/students/' + p.id });
  let open = null;
  const draw = () => {
    const h = d.summary;
    if (!open) {
      open = new Set(d.juz.filter((j) => j.passed > 0 && j.passed < j.surahs.length).map((j) => j.n));
      if (!open.size) { const next = d.juz.find((j) => !j.complete && j.passed === 0); open.add(next ? next.n : 30); }
    }
    view().innerHTML = `
      <div class="card pad"><div class="muted small">${esc(d.student.name)}</div>
        <div class="stat" style="margin-top:2px"><b id="hz-pct">${h.pct}%</b><span class="muted">Корана</span></div>
        <div class="bar" style="margin:10px 0"><i style="width:${Math.max(h.pct, 0.5)}%"></i></div>
        <div class="badges"><span class="badge ok">${nWord(h.surahs, 'сура', 'суры', 'сур')}</span><span class="badge ok">${h.ayahs} из 6236 аятов</span>
          <span class="badge ${h.juz_count ? 'ok' : ''}">${h.juz_count ? nWord(h.juz_count, 'джуз', 'джуза', 'джузов') + ' целиком: ' + h.juz_done.slice().reverse().join(', ') : 'целых джузов пока нет'}</span></div></div>
      <section>${secTitle('Суры по джузам')}
      <div class="card list">${d.juz.map((j) => `<details class="juz" data-juz="${j.n}" ${open.has(j.n) ? 'open' : ''}>
        <summary>${icon('chev', 'chev')}<span>Джуз ${j.n}</span>${j.complete ? `<span class="badge ok">${icon('check')}закончен</span>` : ''}<span class="cnt">${j.passed} из ${j.surahs.length}</span></summary>
        ${j.surahs.map((s) => `<div class="surah ${s.passed ? 'done' : ''}"><span class="no">${s.n}</span><span class="main"><div class="t">${esc(s.name)}</div><div class="s">${nWord(s.ayahs, 'аят', 'аята', 'аятов')}</div></span>
          ${s.passed ? `<button class="done-mark" data-undo="${s.n}" data-name="${esc(s.name)}" aria-label="Сдана, ${GRADE[s.grade]}. Нажмите, чтобы снять отметку">${icon('check')}<span>${GRADE[s.grade]}<br><span class="muted small" style="font-weight:500">${fmtD(s.passed_at)}</span></span></button>`
    : `<button class="btn soft sm" data-pass="${s.n}" data-name="${esc(s.name)}">Сдал</button>`}</div>`).join('')}</details>`).join('')}</div></section>`;
    $$('details.juz').forEach((el) => el.addEventListener('toggle', () => { const n = Number(el.dataset.juz); if (el.open) open.add(n); else open.delete(n); }));
    $$('[data-pass]').forEach((b) => b.addEventListener('click', () => {
      sheet(`${b.dataset.pass}. ${b.dataset.name}`, `<p class="muted" style="margin-bottom:14px">Как ${esc(d.student.name.split(' ')[0])} сдал(а) суру?</p>
        <div class="grade-btns"><button class="btn primary lg" data-g="5">Отлично</button><button class="btn lg" data-g="4">Хорошо</button><button class="btn lg" data-g="3">Удовлетворительно</button></div>`, (body) => {
        $$('[data-g]', body).forEach((g) => g.addEventListener('click', async () => {
          $$('[data-g]', body).forEach((x) => { x.disabled = true; });
          try {
            const before = d.summary;
            d = Object.assign(await POST(`/students/${p.id}/hifz`, { surah: Number(b.dataset.pass), passed: true, grade: Number(g.dataset.g) }), { student: d.student });
            closeSheet(); draw();
            const newJuz = d.summary.juz_done.filter((j) => !before.juz_done.includes(j));
            toast(newJuz.length ? `Машаллах! Джуз ${newJuz[0]} закончен` : `Сура сдана · прогресс ${before.pct}% → ${d.summary.pct}%`);
          } catch (e) { toast(e.message, true); closeSheet(); }
        }));
      });
    }));
    $$('[data-undo]').forEach((b) => b.addEventListener('click', () => confirmSheet('Снять отметку?', `Сура «${b.dataset.name}» снова станет несданной. Запись об этом останется в журнале.`, 'Снять отметку', async () => {
      d = Object.assign(await POST(`/students/${p.id}/hifz`, { surah: Number(b.dataset.undo), passed: false }), { student: d.student });
      draw(); toast('Отметка снята');
    })));
  };
  draw();
});

// ---------- группы ----------
page('/groups', async (p, alive) => {
  const list = await GET('/groups');
  if (!alive()) return;
  setTop(isStaff() ? 'Группы' : 'Мои группы', { actions: isStaff() ? `<button class="btn primary sm" id="add">${icon('plus')}Группа</button>` : '' });
  const card = (g) => `<a class="row" href="#/groups/${g.id}"><span class="lead">${icon('book')}</span><span class="main"><div class="t">${esc(g.name)}</div>
      <div class="s">${isStaff() ? esc(g.teacher_name) + ' · ' : ''}${esc(schedText(g.schedule))}</div>
      <div class="badges" style="margin-top:5px"><span class="badge">${genderGroup(g.gender)}</span><span class="badge ${g.students >= g.capacity ? 'warn' : ''}">${g.students} из ${g.capacity} мест</span>${g.status === 'archived' ? '<span class="badge">в архиве</span>' : ''}</div></span>${chev()}</a>`;
  view().innerHTML = `<div class="card list">${list.map(card).join('') || '<div class="empty">Групп пока нет</div>'}</div>`;
  if ($('#add')) $('#add').addEventListener('click', () => groupForm(null));
});

async function groupForm(g) {
  const meta = await loadMeta();
  const sched = {};
  ((g && g.schedule) || []).forEach((s) => { sched[s.d] = s.t; });
  sheet(g ? 'Изменить группу' : 'Новая группа', `<form>
    <label class="field"><span>Название</span><input type="text" name="name" value="${esc(g ? g.name : '')}" required></label>
    <div class="grid2"><label class="field"><span>Направление</span><select name="direction_id">${meta.directions.map((d) => `<option value="${d.id}" ${g && g.direction_id === d.id ? 'selected' : ''}>${esc(d.name)}</option>`).join('')}</select></label>
      <label class="field"><span>Группа</span><select name="gender"><option value="m">Мужская</option><option value="f" ${g && g.gender === 'f' ? 'selected' : ''}>Женская</option></select></label></div>
    <label class="field"><span>Учитель</span><select name="teacher_id">${meta.teachers.map((t) => `<option value="${t.id}" ${g && g.teacher_id === t.id ? 'selected' : ''}>${esc(t.name)}</option>`).join('')}</select></label>
    <div class="grid2"><label class="field"><span>Стоимость в месяц, ${esc(S.me.currency)}</span><input type="number" name="price" min="0" step="50" inputmode="numeric" value="${g ? g.price : 3000}" required></label>
      <label class="field"><span>Мест</span><input type="number" name="capacity" min="1" max="100" inputmode="numeric" value="${g ? g.capacity : 12}" required></label></div>
    <label class="field"><span>Кабинет</span><input type="text" name="room" value="${esc(g ? g.room : '')}"></label>
    <div class="field"><span>Расписание</span>${[1, 2, 3, 4, 5, 6, 7].map((d) => `<div class="check" style="margin-bottom:6px"><input type="checkbox" id="d${d}" data-day="${d}" ${sched[d] ? 'checked' : ''}><label for="d${d}" style="width:34px">${ISO_DOW[d]}</label><input type="time" data-time="${d}" value="${sched[d] || '16:00'}" aria-label="Время, ${ISO_DOW[d]}" style="max-width:130px"></div>`).join('')}</div>
    <div class="form-error"></div><button type="submit" class="btn primary block">${g ? 'Сохранить' : 'Создать группу'}</button></form>`, (body) => {
    onSubmit($('form', body), async (v) => {
      v.schedule = $$('[data-day]', body).filter((c) => c.checked).map((c) => ({ d: Number(c.dataset.day), t: $(`[data-time="${c.dataset.day}"]`, body).value }));
      if (g) { await PATCH('/groups/' + g.id, v); closeSheet(); toast('Группа сохранена'); S.meta = null; render(); } else {
        const r = await POST('/groups', v); closeSheet(); toast('Группа создана'); S.meta = null; go('/groups/' + r.id);
      }
    });
  });
}

page('/groups/:id', async (p, alive) => {
  const g = await GET('/groups/' + p.id);
  if (!alive()) return;
  setTop('Группа', { back: '/groups' });
  const staff = isStaff();
  view().innerHTML = `
    <div class="card profile"><h2>${esc(g.name)}</h2>
      <div class="meta">${esc(g.direction)} · ${genderGroup(g.gender)}${g.status === 'archived' ? ' · в архиве' : ''}</div>
      <div class="kv"><span>Учитель</span><span>${esc(g.teacher_name)}</span></div>
      <div class="kv"><span>Расписание</span><span>${esc(schedText(g.schedule))}</span></div>
      ${g.room ? `<div class="kv"><span>Кабинет</span><span>${esc(g.room)}</span></div>` : ''}
      <div class="kv"><span>Учеников</span><span>${g.students.length} из ${g.capacity}</span></div>
      ${staff ? `<div class="kv"><span>Стоимость</span><span>${money(g.price)} в месяц</span></div>` : ''}
      ${g.status === 'active' ? `<a class="btn primary lg block" style="margin-top:14px" href="#/attendance/${g.id}/${S.me.today}">Отметить посещаемость${g.today_scheduled ? ' за сегодня' : ''}</a>` : ''}</div>
    <section>${secTitle('Ученики')}
      <div class="card list">${g.students.map((s) => `<a class="row" href="#/students/${s.id}"><span class="main"><div class="t">${esc(s.name)}</div>
        <div class="s">${ageText(s.age)}${hifzShort(s.hifz) ? ' · ' + hifzShort(s.hifz) : ''}</div>
        ${s.absent_streak >= 3 ? `<div class="badges" style="margin-top:5px"><span class="badge danger">${streakText(s.absent_streak)}</span></div>` : ''}</span>
        <span class="small muted num">${s.attendance != null ? 'посещ. ' + s.attendance + '%' : ''}</span>${chev()}</a>`).join('') || '<div class="empty">В группе пока никого нет</div>'}</div></section>
    <section>${secTitle('Последние уроки')}
      <div class="card list">${g.lessons.map((l) => `<a class="row" href="#/attendance/${g.id}/${l.date}"><span class="lead">${icon('calendar')}</span><span class="main"><div class="t">${fmtDL(l.date)}</div><div class="s">Было ${l.present || 0} из ${l.total}</div></span>${chev()}</a>`).join('') || '<div class="empty">Уроков пока не было</div>'}</div></section>
    ${staff ? `<section>${secTitle('Действия')}<div class="card list">
      <button class="row" id="g-edit"><span class="lead">${icon('edit')}</span><span class="main"><div class="t">Изменить группу</div></span></button>
      ${g.status === 'active' ? `<button class="row" id="g-arch"><span class="lead danger">${icon('archive')}</span><span class="main"><div class="t">Перевести в архив</div><div class="s">Только когда в группе не осталось учеников</div></span></button>`
    : `<button class="row" id="g-rest"><span class="lead">${icon('history')}</span><span class="main"><div class="t">Вернуть из архива</div></span></button>`}</div></section>` : ''}`;
  if (!staff) return;
  $('#g-edit').addEventListener('click', () => groupForm(g));
  if ($('#g-arch')) $('#g-arch').addEventListener('click', () => confirmSheet('Группу в архив?', 'Группа исчезнет из списков записи. История уроков сохранится.', 'В архив', async () => { await PATCH('/groups/' + g.id, { status: 'archived' }); S.meta = null; toast('Группа в архиве'); render(); }));
  if ($('#g-rest')) $('#g-rest').addEventListener('click', async () => { try { await PATCH('/groups/' + g.id, { status: 'active' }); S.meta = null; toast('Группа возвращена'); render(); } catch (e) { toast(e.message, true); } });
});

// ---------- посещаемость ----------
const ATT = [['present', 'check', 'был'], ['late', 'clock', 'опоздал'], ['absent', 'x', 'не был'], ['excused', null, 'уважительная причина']];

async function attendancePage(p, alive) {
  const date = p.date || S.me.today;
  const [d] = await Promise.all([GET(`/attendance?group_id=${p.gid}&date=${date}`), S.meta ? null : loadMeta()]);
  if (!alive()) return;
  setTop(d.group.name, { back: S.me.role === 'teacher' ? '/' : '/groups/' + p.gid });
  const g = S.meta.groups.find((x) => String(x.id) === String(p.gid));
  const days = g ? g.schedule.map((s) => s.d) : [];
  const shift = (dir) => {
    const dt = pd(date);
    for (let i = 0; i < 14; i++) {
      dt.setDate(dt.getDate() + dir);
      if (!days.length || days.includes(dt.getDay() || 7)) break;
    }
    return isoD(dt);
  };
  const next = shift(1);
  const marks = {};
  d.students.forEach((s) => { marks[s.id] = s.status || 'present'; });
  const jump = (to) => { history.replaceState(null, '', `#/attendance/${p.gid}/${to}`); render(); };
  view().innerHTML = `
    <div class="date-nav"><button class="icon-btn card" id="prev" aria-label="Предыдущий урок">${icon('back')}</button>
      <input type="date" id="date" value="${date}" max="${S.me.today}" aria-label="Дата урока">
      <button class="icon-btn card" id="next" aria-label="Следующий урок" ${next > S.me.today ? 'disabled style="opacity:.35"' : ''}>${icon('chev')}</button></div>
    <p class="muted small" style="margin:0 2px 10px">${fmtDL(date)}${d.time ? ' · ' + esc(d.time) : ''} · ${d.marked ? 'отмечено, можно исправить' : d.scheduled ? 'ещё не отмечено — по умолчанию все «был»' : 'по расписанию урока в этот день нет'}</p>
    <div class="legend">${ATT.map((a) => `<span>${a[1] ? icon(a[1]) : '<b>У</b>'}${a[2]}</span>`).join('')}</div>
    <div class="card list">${d.students.map((s) => `<div class="att-row"><div class="nm">${esc(s.name)}${s.absent_streak >= 3 ? `<small>${streakText(s.absent_streak)}</small>` : ''}</div>
      <div class="seg" role="group" aria-label="${esc(s.name)}">${ATT.map((a) => `<button data-id="${s.id}" data-s="${a[0]}" aria-label="${a[2]}" aria-pressed="false">${a[1] ? icon(a[1]) : 'У'}</button>`).join('')}</div></div>`).join('') || '<div class="empty">На эту дату в группе никого нет</div>'}</div>
    <div class="foot-space"></div>
    ${d.students.length ? `<div class="foot"><div class="info"><b id="cnt"></b><span class="muted small">присутствуют</span></div><button class="btn primary lg" id="save" style="min-width:150px">Сохранить</button></div>` : ''}`;
  const paint = () => {
    $$('.seg button').forEach((b) => { const on = marks[b.dataset.id] === b.dataset.s; b.classList.toggle('on', on); b.setAttribute('aria-pressed', on); });
    const present = Object.values(marks).filter((s) => s === 'present' || s === 'late').length;
    if ($('#cnt')) $('#cnt').textContent = `${present} из ${d.students.length}`;
  };
  paint();
  $$('.seg button').forEach((b) => b.addEventListener('click', () => { marks[b.dataset.id] = b.dataset.s; paint(); }));
  $('#prev').addEventListener('click', () => jump(shift(-1)));
  $('#next').addEventListener('click', () => { if (next <= S.me.today) jump(next); });
  $('#date').addEventListener('change', (e) => { if (e.target.value) jump(e.target.value); });
  if ($('#save')) {
    $('#save').addEventListener('click', async () => {
      const btn = $('#save');
      btn.disabled = true;
      try {
        const r = await POST('/attendance', { group_id: Number(p.gid), date, marks });
        toast(`Сохранено: ${r.present} из ${r.total} на уроке`);
        goBack(S.me.role === 'teacher' ? '/' : '/groups/' + p.gid);
      } catch (e) { toast(e.message, true); btn.disabled = false; }
    });
  }
}
page('/attendance/:gid/:date', attendancePage);
page('/attendance/:gid', attendancePage);
