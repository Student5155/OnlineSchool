#!/usr/bin/env python3
"""Школа Корана — учёт учеников, посещаемости, хифза и оплат.

Запуск:  python3 app.py        (откроется на http://localhost:8420)
Нужен только Python 3.8+, без установки пакетов. Данные — в data/school.db.
"""
import datetime as dt
import json
import mimetypes
import os
import re
import secrets
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import core
import db
import seed
from db import one, q, run, val
from quran import AYAHS, JUZ_OF_SURAH, JUZ_SURAHS, NAMES

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
DEMO_LOGIN = os.environ.get("DEMO_LOGIN", "1") != "0"

OWNER = ("owner",)
STAFF = ("owner", "admin")
ALL = ("owner", "admin", "teacher")
PUBLIC = None
ROUTES = []

STATUSES = ("present", "late", "absent", "excused")
STAGES = ("new", "contacted", "trial", "enrolled", "declined")
METHODS = ("cash", "transfer", "card")
ROLE_LABEL = {"owner": "владелец", "admin": "администратор", "teacher": "учитель"}


class ApiError(Exception):
    def __init__(self, status, message):
        Exception.__init__(self, message)
        self.status, self.message = status, message


def route(method, pattern, roles):
    rx = re.compile("^" + pattern + "$")

    def deco(fn):
        ROUTES.append((method, rx, roles, fn))
        return fn
    return deco


class Ctx(object):
    def __init__(self, user, body, query):
        self.user, self.body, self.query = user, body, query
        self.set_cookie = None

    @property
    def is_teacher(self):
        return self.user["role"] == "teacher"

    def arg(self, name, default=None):
        return self.query.get(name, [default])[0]


# ---------- проверка входных данных ----------
def text(b, key, required=False, maxlen=200):
    v = str(b.get(key) or "").strip()
    if required and not v:
        raise ApiError(422, "Заполните поле: %s" % FIELD.get(key, key))
    return v[:maxlen]


def integer(v, name="значение", lo=None, hi=None):
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise ApiError(422, "Неверное число: %s" % name)
    if (lo is not None and n < lo) or (hi is not None and n > hi):
        raise ApiError(422, "Недопустимое значение: %s" % name)
    return n


def date_of(v, name="дата", required=True):
    if not v:
        if required:
            raise ApiError(422, "Укажите: %s" % name)
        return None
    try:
        return dt.date.fromisoformat(str(v))
    except ValueError:
        raise ApiError(422, "Неверная дата: %s" % name)


def choice(v, options, name):
    if v not in options:
        raise ApiError(422, "Недопустимое значение: %s" % name)
    return v


FIELD = {"first_name": "имя", "last_name": "фамилия", "parent_name": "имя родителя", "parent_phone": "телефон",
         "name": "название", "child_first": "имя ребёнка", "child_last": "фамилия ребёнка", "phone": "телефон",
         "reason": "причина", "login": "логин", "password": "пароль"}


def audit(c, action, details=""):
    run("INSERT INTO audit (user_id, user_name, action, details, at) VALUES (?,?,?,?,?)",
        c.user["id"], c.user["name"], action, details, core.now())


def full(r):
    return "%s %s" % (r["first_name"], r["last_name"])


def digits(s):
    d = re.sub(r"\D", "", s or "")
    return d[-10:]


# ---------- границы доступа учителя ----------
def my_group_ids(c):
    return [r["id"] for r in q("SELECT id FROM groups WHERE teacher_id=?", c.user["teacher_id"])]


def get_group(c, gid):
    g = one("""SELECT g.*, d.name direction, t.name teacher_name FROM groups g
               JOIN directions d ON d.id = g.direction_id JOIN teachers t ON t.id = g.teacher_id WHERE g.id=?""", gid)
    if not g:
        raise ApiError(404, "Группа не найдена")
    if c.is_teacher and g["teacher_id"] != c.user["teacher_id"]:
        raise ApiError(403, "Это не ваша группа")
    return g


def get_student(c, sid):
    s = one("SELECT * FROM students WHERE id=?", sid)
    if not s:
        raise ApiError(404, "Ученик не найден")
    if c.is_teacher and not val("""SELECT 1 FROM enrollments e JOIN groups g ON g.id = e.group_id
                                   WHERE e.student_id=? AND e.status='active' AND g.teacher_id=?""",
                                sid, c.user["teacher_id"]):
        raise ApiError(403, "Это не ваш ученик")
    return s


def group_json(g, c):
    out = {"id": g["id"], "name": g["name"], "direction": g["direction"], "direction_id": g["direction_id"],
           "gender": g["gender"], "teacher_id": g["teacher_id"], "teacher_name": g["teacher_name"],
           "schedule": core.schedule_of(g), "room": g["room"], "capacity": g["capacity"], "status": g["status"]}
    if not c.is_teacher:
        out["price"] = g["price"]
    return out


# ---------- вход ----------
def user_json(u):
    return {"id": u["id"], "name": u["name"], "role": u["role"], "teacher_id": u["teacher_id"],
            "school_name": core.setting("school_name"), "currency": core.setting("currency"),
            "today": core.today().isoformat()}


def start_session(c, u):
    token = secrets.token_urlsafe(32)
    run("DELETE FROM sessions WHERE expires_at < ?", core.now())
    run("INSERT INTO sessions (token, user_id, expires_at) VALUES (?,?,?)", token, u["id"],
        (dt.datetime.now() + dt.timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S"))
    c.set_cookie = "sid=%s; Path=/; HttpOnly; SameSite=Lax; Max-Age=1209600" % token
    return user_json(u)


@route("GET", "/api/public", PUBLIC)
def public_info(c):
    demo = []
    if DEMO_LOGIN:
        for login_name in ("abdullah", "maryam", "yusuf", "aisha"):
            r = one("SELECT login, name, role, teacher_id FROM users WHERE login=? AND is_demo=1 AND status='active'", login_name)
            if not r:
                continue
            gender = val("SELECT gender FROM teachers WHERE id=?", r["teacher_id"]) if r["teacher_id"] else None
            label = "учительница" if gender == "f" else ROLE_LABEL[r["role"]]
            demo.append({"login": r["login"], "name": r["name"], "role": r["role"], "label": label})
    return {"school_name": core.setting("school_name"), "demo": demo}


@route("POST", "/api/login", PUBLIC)
def login(c):
    u = one("SELECT * FROM users WHERE login=? AND status='active'", text(c.body, "login").lower())
    if not u or not core.check_password(c.body.get("password") or "", u["pass_hash"]):
        raise ApiError(401, "Неверный логин или пароль")
    return start_session(c, u)


@route("POST", "/api/demo-login", PUBLIC)
def demo_login(c):
    if not DEMO_LOGIN:
        raise ApiError(403, "Демо-вход отключён")
    u = one("SELECT * FROM users WHERE login=? AND is_demo=1 AND status='active'", text(c.body, "login"))
    if not u:
        raise ApiError(404, "Нет такой демо-записи")
    return start_session(c, u)


@route("POST", "/api/logout", ALL)
def logout(c):
    run("DELETE FROM sessions WHERE user_id=? AND token=?", c.user["id"], c.user["_token"])
    c.set_cookie = "sid=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"
    return {"ok": True}


@route("GET", "/api/me", PUBLIC)
def me(c):
    return user_json(c.user) if c.user else None


@route("GET", "/api/meta", ALL)
def meta(c):
    """Справочники для форм."""
    groups = q("""SELECT g.*, d.name direction, t.name teacher_name FROM groups g
                  JOIN directions d ON d.id = g.direction_id JOIN teachers t ON t.id = g.teacher_id
                  WHERE g.status='active' ORDER BY g.gender DESC, g.name""")
    if c.is_teacher:
        groups = [g for g in groups if g["teacher_id"] == c.user["teacher_id"]]
    counts = {r["group_id"]: r["n"] for r in
              q("SELECT group_id, COUNT(*) n FROM enrollments WHERE status='active' GROUP BY group_id")}
    out = {"groups": [dict(group_json(g, c), students=counts.get(g["id"], 0)) for g in groups],
           "directions": q("SELECT id, name FROM directions ORDER BY id")}
    if not c.is_teacher:
        out["teachers"] = q("SELECT id, name, gender FROM teachers WHERE status='active' ORDER BY name")
    return out


# ---------- главный экран ----------
def todays_lessons(group_ids=None):
    today = core.today()
    out = []
    for g in q("""SELECT g.*, t.name teacher_name FROM groups g JOIN teachers t ON t.id = g.teacher_id
                  WHERE g.status='active'"""):
        if group_ids is not None and g["id"] not in group_ids:
            continue
        t = core.lesson_time(g, today)
        if t is None:
            continue
        total = val("SELECT COUNT(*) FROM enrollments WHERE group_id=? AND status='active'", g["id"])
        lesson = one("SELECT id FROM lessons WHERE group_id=? AND date=?", g["id"], today.isoformat())
        present = None
        if lesson:
            present = val("SELECT COUNT(*) FROM attendance WHERE lesson_id=? AND status IN ('present','late')", lesson["id"])
        out.append({"group_id": g["id"], "group": g["name"], "time": t, "teacher": g["teacher_name"], "room": g["room"],
                    "total": total, "marked": bool(lesson), "present": present})
    out.sort(key=lambda x: x["time"])
    return out


def unmarked_lessons(group_ids=None, days=7):
    today = core.today()
    out = []
    for g in q("SELECT g.*, t.name teacher_name FROM groups g JOIN teachers t ON t.id = g.teacher_id WHERE g.status='active'"):
        if group_ids is not None and g["id"] not in group_ids:
            continue
        marked = {r["date"] for r in q("SELECT date FROM lessons WHERE group_id=? AND date>=?", g["id"],
                                       (today - dt.timedelta(days=days)).isoformat())}
        for i in range(1, days + 1):
            d = today - dt.timedelta(days=i)
            if core.lesson_time(g, d) is not None and d.isoformat() not in marked:
                out.append({"group_id": g["id"], "group": g["name"], "teacher": g["teacher_name"], "date": d.isoformat()})
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


@route("GET", "/api/dashboard", ALL)
def dashboard(c):
    today = core.today()
    cur = core.month_of(today)
    gids = my_group_ids(c) if c.is_teacher else None
    week = (today - dt.timedelta(days=6), today)
    prev = (today - dt.timedelta(days=13), today - dt.timedelta(days=7))
    out = {"today": today.isoformat(), "month": cur, "month_label": core.month_label(cur),
           "lessons": todays_lessons(gids), "absent3": core.absent_streaks(gids),
           "unmarked": unmarked_lessons(gids),
           "attendance": {"week": core.attendance_rate(week[0], week[1], gids),
                          "prev_week": core.attendance_rate(prev[0], prev[1], gids)}}
    if c.is_teacher:
        groups = q("""SELECT g.*, d.name direction, t.name teacher_name FROM groups g JOIN directions d ON d.id = g.direction_id
                      JOIN teachers t ON t.id = g.teacher_id WHERE g.teacher_id=? AND g.status='active' ORDER BY g.name""",
                   c.user["teacher_id"])
        out["groups"] = [dict(group_json(g, c), students=val(
            "SELECT COUNT(*) FROM enrollments WHERE group_id=? AND status='active'", g["id"])) for g in groups]
        out["students"] = val("""SELECT COUNT(DISTINCT e.student_id) FROM enrollments e JOIN groups g ON g.id = e.group_id
                                 WHERE e.status='active' AND g.teacher_id=?""", c.user["teacher_id"])
        return out

    core.ensure_charges(cur)
    first = core.month_bounds(cur)[0].isoformat()
    out["students"] = val("SELECT COUNT(*) FROM students WHERE status='active'")
    out["students_new"] = val("SELECT COUNT(*) FROM students WHERE status='active' AND joined_at>=?", first)
    out["students_left"] = val("SELECT COUNT(*) FROM students WHERE status='archived' AND archived_at>=?", first)
    out["groups"] = val("SELECT COUNT(*) FROM groups WHERE status='active'")
    out["free"] = val("SELECT COUNT(*) FROM students WHERE status='active' AND is_free=1")
    out["applications_new"] = val("SELECT COUNT(*) FROM applications WHERE stage='new'")
    out["applications_open"] = val("SELECT COUNT(*) FROM applications WHERE stage IN ('new','contacted','trial')")
    months = []
    for m in (core.add_months(cur, -2), core.add_months(cur, -1), cur):
        months.append({"month": m, "label": core.month_label(m).split(" ")[0],
                       "expected": val("SELECT COALESCE(SUM(amount),0) FROM charges WHERE month=?", m),
                       "collected": val("""SELECT COALESCE(SUM(p.amount),0) FROM payments p JOIN charges ch ON ch.id = p.charge_id
                                           WHERE ch.month=? AND p.status='active'""", m)})
    debts = core.open_charges()
    out["finance"] = {"months": months, "expected": months[-1]["expected"], "collected": months[-1]["collected"],
                      "debt": sum(d["due"] for d in debts),
                      "debt_overdue": sum(d["due"] for d in debts if d["month"] < cur),
                      "debt_families": len({d["family_id"] for d in debts})}
    if c.user["role"] == "owner":
        due = 0
        for m in (core.add_months(cur, -2), core.add_months(cur, -1), cur):
            due += sum(max(r["due"], 0) for r in core.salary_report(m))
        out["salary_due"] = due
    return out


# ---------- группы ----------
@route("GET", "/api/groups", ALL)
def groups_list(c):
    rows = q("""SELECT g.*, d.name direction, t.name teacher_name FROM groups g
                JOIN directions d ON d.id = g.direction_id JOIN teachers t ON t.id = g.teacher_id
                ORDER BY g.status, g.gender DESC, g.name""")
    if c.is_teacher:
        rows = [g for g in rows if g["teacher_id"] == c.user["teacher_id"] and g["status"] == "active"]
    counts = {r["group_id"]: r["n"] for r in
              q("SELECT group_id, COUNT(*) n FROM enrollments WHERE status='active' GROUP BY group_id")}
    return [dict(group_json(g, c), students=counts.get(g["id"], 0)) for g in rows]


@route("GET", r"/api/groups/(\d+)", ALL)
def group_detail(c, gid):
    g = get_group(c, int(gid))
    studs = q("""SELECT s.id, s.first_name, s.last_name, s.birth_date, e.id enrollment_id, e.start_date
                 FROM enrollments e JOIN students s ON s.id = e.student_id
                 WHERE e.group_id=? AND e.status='active' ORDER BY s.first_name, s.last_name""", g["id"])
    ids = [s["id"] for s in studs]
    att = core.student_attendance(ids, [g["id"]])
    streak = {s["student_id"]: s["count"] for s in core.absent_streaks([g["id"]])}
    hz = core.hifz_summaries(ids)
    out = group_json(g, c)
    out["students"] = [{"id": s["id"], "name": full(s), "age": core.age(s["birth_date"]),
                        "enrollment_id": s["enrollment_id"], "attendance": att.get(s["id"]),
                        "absent_streak": streak.get(s["id"], 0), "hifz": hz[s["id"]]} for s in studs]
    out["lessons"] = q("""SELECT l.date, SUM(a.status IN ('present','late')) present, COUNT(a.id) total
                          FROM lessons l LEFT JOIN attendance a ON a.lesson_id = l.id
                          WHERE l.group_id=? GROUP BY l.id ORDER BY l.date DESC LIMIT 8""", g["id"])
    out["today_scheduled"] = core.lesson_time(g, core.today()) is not None
    return out


def group_fields(c, existing=None):
    b = c.body
    f = {}
    f["name"] = text(b, "name", required=True)
    f["direction_id"] = integer(b.get("direction_id"), "направление")
    if not val("SELECT 1 FROM directions WHERE id=?", f["direction_id"]):
        raise ApiError(422, "Нет такого направления")
    f["gender"] = choice(b.get("gender"), ("m", "f"), "мужская/женская")
    f["teacher_id"] = integer(b.get("teacher_id"), "учитель")
    if not val("SELECT 1 FROM teachers WHERE id=? AND status='active'", f["teacher_id"]):
        raise ApiError(422, "Учитель не найден или в архиве")
    f["price"] = integer(b.get("price"), "стоимость в месяц", 0, 1000000)
    f["capacity"] = integer(b.get("capacity") or 12, "мест в группе", 1, 100)
    f["room"] = text(b, "room")
    sched = []
    for s in b.get("schedule") or []:
        d = integer(s.get("d"), "день недели", 1, 7)
        t = str(s.get("t") or "")
        if not re.match(r"^\d\d:\d\d$", t):
            raise ApiError(422, "Время урока укажите как ЧЧ:ММ")
        sched.append({"d": d, "t": t})
    f["schedule"] = json.dumps(sorted(sched, key=lambda x: x["d"]))
    if existing and f["gender"] != existing["gender"] and val(
            "SELECT COUNT(*) FROM enrollments WHERE group_id=? AND status='active'", existing["id"]):
        raise ApiError(422, "В группе есть ученики — сменить «мужская/женская» нельзя")
    return f


@route("POST", "/api/groups", STAFF)
def group_create(c):
    f = group_fields(c)
    gid = run("""INSERT INTO groups (name, direction_id, gender, teacher_id, price, capacity, room, schedule)
                 VALUES (?,?,?,?,?,?,?,?)""", f["name"], f["direction_id"], f["gender"], f["teacher_id"], f["price"],
              f["capacity"], f["room"], f["schedule"])
    audit(c, "Создана группа", f["name"])
    return {"id": gid}


@route("PATCH", r"/api/groups/(\d+)", STAFF)
def group_update(c, gid):
    g = get_group(c, int(gid))
    if "status" in c.body:
        status = choice(c.body["status"], ("active", "archived"), "статус")
        if status == "archived" and val("SELECT COUNT(*) FROM enrollments WHERE group_id=? AND status='active'", g["id"]):
            raise ApiError(422, "В группе есть ученики. Сначала переведите их в другие группы.")
        run("UPDATE groups SET status=? WHERE id=?", status, g["id"])
        audit(c, "Группа в архиве" if status == "archived" else "Группа возвращена из архива", g["name"])
        return {"ok": True}
    f = group_fields(c, g)
    run("""UPDATE groups SET name=?, direction_id=?, gender=?, teacher_id=?, price=?, capacity=?, room=?, schedule=?
           WHERE id=?""", f["name"], f["direction_id"], f["gender"], f["teacher_id"], f["price"], f["capacity"],
        f["room"], f["schedule"], g["id"])
    audit(c, "Изменена группа", f["name"])
    return {"ok": True}


# ---------- запись в группу ----------
def check_enroll(student, group_id):
    """Главное правило: девочки — только в женские группы, мальчики — только в мужские."""
    g = one("SELECT * FROM groups WHERE id=?", group_id)
    if not g:
        raise ApiError(404, "Группа не найдена")
    if g["status"] != "active":
        raise ApiError(422, "Группа «%s» в архиве" % g["name"])
    if g["gender"] != student["gender"]:
        if student["gender"] == "f":
            raise ApiError(422, "Нельзя записать девочку в мужскую группу «%s». Выберите женскую группу." % g["name"])
        raise ApiError(422, "Нельзя записать мальчика в женскую группу «%s». Выберите мужскую группу." % g["name"])
    if student.get("id") and val("SELECT 1 FROM enrollments WHERE student_id=? AND group_id=? AND status='active'",
                                 student["id"], g["id"]):
        raise ApiError(422, "Ученик уже занимается в группе «%s»" % g["name"])
    if val("SELECT COUNT(*) FROM enrollments WHERE group_id=? AND status='active'", g["id"]) >= g["capacity"]:
        raise ApiError(422, "В группе «%s» нет свободных мест" % g["name"])
    return g


def do_enroll(c, student, group_id):
    g = check_enroll(student, group_id)
    if student["status"] != "active":
        raise ApiError(422, "Ученик в архиве — сначала верните его")
    eid = run("INSERT INTO enrollments (student_id, group_id, start_date) VALUES (?,?,?)",
              student["id"], g["id"], core.today().isoformat())
    core.ensure_charges(core.month_of(core.today()))
    audit(c, "Запись в группу", "%s → %s" % (full(student), g["name"]))
    return eid


@route("POST", "/api/enrollments", STAFF)
def enrollment_create(c):
    s = get_student(c, integer(c.body.get("student_id"), "ученик"))
    return {"id": do_enroll(c, s, integer(c.body.get("group_id"), "группа"))}


@route("POST", r"/api/enrollments/(\d+)/end", STAFF)
def enrollment_end(c, eid):
    e = one("""SELECT e.*, s.first_name, s.last_name, g.name group_name FROM enrollments e
               JOIN students s ON s.id = e.student_id JOIN groups g ON g.id = e.group_id WHERE e.id=?""", int(eid))
    if not e or e["status"] != "active":
        raise ApiError(404, "Запись в группу не найдена")
    run("UPDATE enrollments SET status='ended', end_date=? WHERE id=?", core.today().isoformat(), e["id"])
    audit(c, "Отчислен из группы", "%s ← %s" % (full(e), e["group_name"]))
    return {"ok": True}


# ---------- ученики ----------
@route("GET", "/api/students", ALL)
def students_list(c):
    status = choice(c.arg("status", "active"), ("active", "archived"), "статус")
    if c.is_teacher:
        status = "active"
    rows = q("""SELECT s.*, f.name family_name FROM students s JOIN families f ON f.id = s.family_id
                WHERE s.status=? ORDER BY s.first_name, s.last_name""", status)
    enr = {}
    for e in q("""SELECT e.student_id, g.id, g.name, g.teacher_id FROM enrollments e JOIN groups g ON g.id = e.group_id
                  WHERE e.status='active' ORDER BY g.name"""):
        if c.is_teacher and e["teacher_id"] != c.user["teacher_id"]:
            continue
        enr.setdefault(e["student_id"], []).append({"id": e["id"], "name": e["name"]})
    if c.is_teacher:
        rows = [s for s in rows if s["id"] in enr]
    gids = my_group_ids(c) if c.is_teacher else None
    ids = [s["id"] for s in rows]
    att = core.student_attendance(ids, gids)
    streak = {}
    for s in core.absent_streaks(gids):
        streak[s["student_id"]] = max(streak.get(s["student_id"], 0), s["count"])
    hz = core.hifz_summaries(ids)
    debt = {}
    if not c.is_teacher:
        for d in core.open_charges():
            debt[d["student_id"]] = debt.get(d["student_id"], 0) + d["due"]
    out = []
    for s in rows:
        item = {"id": s["id"], "name": full(s), "gender": s["gender"], "age": core.age(s["birth_date"]),
                "status": s["status"], "groups": enr.get(s["id"], []), "attendance": att.get(s["id"]),
                "absent_streak": streak.get(s["id"], 0), "hifz": hz[s["id"]]}
        if not c.is_teacher:
            item.update(family_id=s["family_id"], family_name=s["family_name"], is_free=bool(s["is_free"]),
                        debt=debt.get(s["id"], 0), archive_reason=s["archive_reason"])
        out.append(item)
    return out


@route("GET", r"/api/students/(\d+)", ALL)
def student_detail(c, sid):
    s = get_student(c, int(sid))
    fam = one("SELECT * FROM families WHERE id=?", s["family_id"])
    gids = my_group_ids(c) if c.is_teacher else None
    enr = q("""SELECT e.id enrollment_id, e.start_date, g.id, g.name, g.teacher_id, t.name teacher_name
               FROM enrollments e JOIN groups g ON g.id = e.group_id JOIN teachers t ON t.id = g.teacher_id
               WHERE e.student_id=? AND e.status='active' ORDER BY g.name""", s["id"])
    if c.is_teacher:
        enr = [e for e in enr if e["id"] in gids]
    marks = q("""SELECT l.date, l.group_id, g.name group_name, a.status FROM attendance a
                 JOIN lessons l ON l.id = a.lesson_id JOIN groups g ON g.id = l.group_id
                 WHERE a.student_id=? ORDER BY l.date DESC LIMIT 60""", s["id"])
    if c.is_teacher:
        marks = [m for m in marks if m["group_id"] in gids]
    streak = [x for x in core.absent_streaks(gids) if x["student_id"] == s["id"]]
    out = {"id": s["id"], "first_name": s["first_name"], "last_name": s["last_name"], "name": full(s),
           "gender": s["gender"], "birth_date": s["birth_date"], "age": core.age(s["birth_date"]),
           "status": s["status"], "joined_at": s["joined_at"], "note": s["note"],
           "archived_at": s["archived_at"], "archive_reason": s["archive_reason"],
           "groups": enr, "hifz": core.hifz_summary(s["id"]),
           "attendance": {"pct": core.student_attendance([s["id"]], gids).get(s["id"]), "marks": marks[:14],
                          "absent_streak": max([x["count"] for x in streak] or [0])},
           "contact": {"name": fam["parent_name"], "phone": fam["parent_phone"]}}
    if not c.is_teacher:
        out["family"] = {"id": fam["id"], "name": fam["name"]}
        out["is_free"] = bool(s["is_free"])
        out["free_reason"] = s["free_reason"]
        out["charges"] = q("""SELECT ch.id, ch.month, ch.base, ch.discount_pct, ch.discount_reason, ch.amount,
                                     g.name group_name,
                                     COALESCE((SELECT SUM(p.amount) FROM payments p
                                               WHERE p.charge_id = ch.id AND p.status='active'), 0) paid
                              FROM charges ch JOIN groups g ON g.id = ch.group_id
                              WHERE ch.student_id=? ORDER BY ch.month DESC, g.name LIMIT 12""", s["id"])
        for ch in out["charges"]:
            ch["month_label"] = core.month_label(ch["month"])
    return out


def find_or_create_family(c, b, last_name):
    if b.get("family_id"):
        fam = one("SELECT * FROM families WHERE id=?", integer(b["family_id"], "семья"))
        if not fam:
            raise ApiError(404, "Семья не найдена")
        return fam["id"], False
    parent, ph = text(b, "parent_name", required=True), text(b, "parent_phone", required=True)
    for fam in q("SELECT id, parent_phone, parent2_phone FROM families WHERE status='active'"):
        if digits(ph) and digits(ph) in (digits(fam["parent_phone"]), digits(fam["parent2_phone"])):
            return fam["id"], False  # тот же телефон родителя — та же семья, скидка посчитается сама
    fid = run("INSERT INTO families (name, parent_name, parent_gender, parent_phone) VALUES (?,?,?,?)",
              "Семья " + last_name, parent, choice(b.get("parent_gender") or "f", ("m", "f"), "родитель"), ph)
    return fid, True


@route("POST", "/api/students", STAFF)
def student_create(c):
    b = c.body
    first, last = text(b, "first_name", required=True), text(b, "last_name", required=True)
    gender = choice(b.get("gender"), ("m", "f"), "пол")
    birth = date_of(b.get("birth_date"), "дата рождения", required=False)
    if b.get("group_id"):
        check_enroll({"gender": gender}, integer(b["group_id"], "группа"))  # до записи чего-либо в базу
    fid, _ = find_or_create_family(c, b, last)
    sid = run("INSERT INTO students (family_id, first_name, last_name, gender, birth_date, joined_at) VALUES (?,?,?,?,?,?)",
              fid, first, last, gender, birth.isoformat() if birth else None, core.today().isoformat())
    audit(c, "Добавлен ученик", "%s %s" % (first, last))
    if b.get("group_id"):
        do_enroll(c, one("SELECT * FROM students WHERE id=?", sid), int(b["group_id"]))
    return {"id": sid, "family_id": fid}


@route("PATCH", r"/api/students/(\d+)", STAFF)
def student_update(c, sid):
    s = get_student(c, int(sid))
    b = c.body
    if "status" in b:
        status = choice(b["status"], ("active", "archived"), "статус")
        if status == "archived":
            reason = text(b, "reason", required=True)
            today = core.today().isoformat()
            run("UPDATE students SET status='archived', archived_at=?, archive_reason=? WHERE id=?", today, reason, s["id"])
            run("UPDATE enrollments SET status='ended', end_date=? WHERE student_id=? AND status='active'", today, s["id"])
            audit(c, "Ученик переведён в архив", "%s — %s" % (full(s), reason))
        else:
            run("UPDATE students SET status='active', archived_at=NULL, archive_reason='' WHERE id=?", s["id"])
            audit(c, "Ученик возвращён из архива", full(s))
        return {"ok": True}
    if "is_free" in b:
        if c.user["role"] != "owner":
            raise ApiError(403, "Бесплатное обучение назначает только владелец")
        free = 1 if b["is_free"] else 0
        run("UPDATE students SET is_free=?, free_reason=? WHERE id=?", free, text(b, "free_reason") if free else "", s["id"])
        audit(c, "Бесплатное обучение: " + ("да" if free else "нет"), full(s))
        return {"ok": True}
    first, last = text(b, "first_name", required=True), text(b, "last_name", required=True)
    birth = date_of(b.get("birth_date"), "дата рождения", required=False)
    run("UPDATE students SET first_name=?, last_name=?, birth_date=?, note=? WHERE id=?", first, last,
        birth.isoformat() if birth else None, text(b, "note", maxlen=1000), s["id"])
    audit(c, "Изменены данные ученика", "%s %s" % (first, last))
    return {"ok": True}


# ---------- посещаемость ----------
@route("GET", "/api/attendance", ALL)
def attendance_get(c):
    g = get_group(c, integer(c.arg("group_id"), "группа"))
    d = date_of(c.arg("date") or core.today().isoformat())
    lesson = one("SELECT * FROM lessons WHERE group_id=? AND date=?", g["id"], d.isoformat())
    marks = {}
    if lesson:
        marks = {r["student_id"]: r["status"] for r in q("SELECT student_id, status FROM attendance WHERE lesson_id=?", lesson["id"])}
    studs = q("""SELECT s.id, s.first_name, s.last_name FROM enrollments e JOIN students s ON s.id = e.student_id
                 WHERE e.group_id=? AND e.start_date<=? AND (e.end_date IS NULL OR e.end_date>=?)
                 ORDER BY s.first_name, s.last_name""", g["id"], d.isoformat(), d.isoformat())
    streak = {s["student_id"]: s["count"] for s in core.absent_streaks([g["id"]])}
    return {"group": {"id": g["id"], "name": g["name"]}, "date": d.isoformat(), "marked": bool(lesson),
            "scheduled": core.lesson_time(g, d) is not None, "time": core.lesson_time(g, d),
            "students": [{"id": s["id"], "name": full(s), "status": marks.get(s["id"]),
                          "absent_streak": streak.get(s["id"], 0)} for s in studs]}


@route("POST", "/api/attendance", ALL)
def attendance_save(c):
    g = get_group(c, integer(c.body.get("group_id"), "группа"))
    d = date_of(c.body.get("date"))
    today = core.today()
    if d > today:
        raise ApiError(422, "Нельзя отметить урок, которого ещё не было")
    if c.is_teacher and d < today - dt.timedelta(days=14):
        raise ApiError(422, "Учитель может править посещаемость только за последние 14 дней. Обратитесь к администратору.")
    marks = c.body.get("marks") or {}
    if not isinstance(marks, dict) or not marks:
        raise ApiError(422, "Отметьте хотя бы одного ученика")
    allowed = {r["student_id"] for r in q("""SELECT student_id FROM enrollments WHERE group_id=? AND start_date<=?
                                             AND (end_date IS NULL OR end_date>=?)""", g["id"], d.isoformat(), d.isoformat())}
    lesson = one("SELECT id FROM lessons WHERE group_id=? AND date=?", g["id"], d.isoformat())
    if lesson:
        lid = lesson["id"]
        run("UPDATE lessons SET marked_by=?, marked_at=? WHERE id=?", c.user["id"], core.now(), lid)
    else:
        lid = run("INSERT INTO lessons (group_id, date, teacher_id, marked_by, marked_at) VALUES (?,?,?,?,?)",
                  g["id"], d.isoformat(), g["teacher_id"], c.user["id"], core.now())
    n = 0
    for sid, status in marks.items():
        sid = integer(sid, "ученик")
        if sid not in allowed:
            raise ApiError(422, "Ученик не числится в этой группе на %s" % d.isoformat())
        choice(status, STATUSES, "отметка")
        run("""INSERT INTO attendance (lesson_id, student_id, status) VALUES (?,?,?)
               ON CONFLICT (lesson_id, student_id) DO UPDATE SET status = excluded.status""", lid, sid, status)
        n += 1
    present = sum(1 for s in marks.values() if s in ("present", "late"))
    audit(c, "Посещаемость", "%s, %s: %d из %d" % (g["name"], d.isoformat(), present, n))
    return {"ok": True, "present": present, "total": n}


# ---------- хифз ----------
def hifz_payload(sid):
    rows = {r["surah"]: r for r in q("SELECT surah, status, grade, passed_at FROM hifz WHERE student_id=?", sid)}
    passed = {n for n, r in rows.items() if r["status"] == "passed"}
    juz = []
    for j in range(30, 0, -1):
        surahs = []
        for n in range(1, 115):
            if JUZ_OF_SURAH[n] != j:
                continue
            r = rows.get(n)
            surahs.append({"n": n, "name": NAMES[n], "ayahs": AYAHS[n], "passed": n in passed,
                           "grade": r["grade"] if r and n in passed else None,
                           "passed_at": r["passed_at"] if r and n in passed else None})
        if surahs:
            surahs.sort(key=lambda x: -x["n"])
            juz.append({"n": j, "complete": all(s in passed for s in JUZ_SURAHS[j]),
                        "passed": sum(1 for s in surahs if s["passed"]), "surahs": surahs})
    return {"summary": core.hifz_summary(sid, passed), "juz": juz}


@route("GET", r"/api/students/(\d+)/hifz", ALL)
def hifz_get(c, sid):
    s = get_student(c, int(sid))
    out = hifz_payload(s["id"])
    out["student"] = {"id": s["id"], "name": full(s)}
    return out


@route("POST", r"/api/students/(\d+)/hifz", ALL)
def hifz_set(c, sid):
    s = get_student(c, int(sid))
    surah = integer(c.body.get("surah"), "сура", 1, 114)
    if c.body.get("passed", True):
        grade = integer(c.body.get("grade") or 5, "оценка", 3, 5)
        run("""INSERT INTO hifz (student_id, surah, status, grade, passed_at, teacher_id, marked_by)
               VALUES (?,?,'passed',?,?,?,?)
               ON CONFLICT (student_id, surah) DO UPDATE SET status='passed', grade=excluded.grade,
               passed_at=excluded.passed_at, teacher_id=excluded.teacher_id, marked_by=excluded.marked_by""",
            s["id"], surah, grade, core.today().isoformat(), c.user["teacher_id"], c.user["id"])
        audit(c, "Сдана сура", "%s — %d. %s (оценка %d)" % (full(s), surah, NAMES[surah], grade))
    else:
        run("UPDATE hifz SET status='revoked', marked_by=? WHERE student_id=? AND surah=?", c.user["id"], s["id"], surah)
        audit(c, "Отметка о сдаче суры снята", "%s — %d. %s" % (full(s), surah, NAMES[surah]))
    return hifz_payload(s["id"])


# ---------- семьи и оплаты ----------
def family_payload(fid):
    fam = one("SELECT * FROM families WHERE id=?", fid)
    if not fam:
        raise ApiError(404, "Семья не найдена")
    kids = q("SELECT * FROM students WHERE family_id=? ORDER BY status, joined_at, id", fid)
    enr = {}
    for e in q("""SELECT e.student_id, g.name FROM enrollments e JOIN groups g ON g.id = e.group_id
                  JOIN students s ON s.id = e.student_id WHERE s.family_id=? AND e.status='active'""", fid):
        enr.setdefault(e["student_id"], []).append(e["name"])
    opened = core.open_charges(family_id=fid)
    for ch in opened:
        ch["student"] = ch.pop("first_name") + " " + ch.pop("last_name")
    pays = q("""SELECT p.id, p.amount, p.method, p.paid_at, p.status, p.cancel_reason, p.batch, ch.month,
                       s.first_name, g.name group_name, u.name by_name
                FROM payments p JOIN charges ch ON ch.id = p.charge_id JOIN students s ON s.id = p.student_id
                JOIN groups g ON g.id = ch.group_id LEFT JOIN users u ON u.id = p.created_by
                WHERE p.family_id=? ORDER BY p.paid_at DESC, p.id DESC LIMIT 40""", fid)
    for p in pays:
        p["month_label"] = core.month_label(p["month"])
    last_rem = one("""SELECT r.created_at, u.name by_name FROM reminders r LEFT JOIN users u ON u.id = r.created_by
                      WHERE r.family_id=? ORDER BY r.id DESC LIMIT 1""", fid)
    return {"id": fam["id"], "name": fam["name"], "parent_name": fam["parent_name"], "parent_gender": fam["parent_gender"],
            "parent_phone": fam["parent_phone"], "parent2_name": fam["parent2_name"], "parent2_phone": fam["parent2_phone"],
            "note": fam["note"], "status": fam["status"],
            "children": [{"id": k["id"], "name": full(k), "first_name": k["first_name"], "status": k["status"],
                          "is_free": bool(k["is_free"]), "groups": enr.get(k["id"], [])} for k in kids],
            "open": opened, "due": sum(ch["due"] for ch in opened), "payments": pays, "last_reminder": last_rem,
            "discounts": {"second": int(core.setting("discount2")), "third": int(core.setting("discount3"))}}


@route("GET", "/api/families", STAFF)
def families_list(c):
    core.ensure_charges(core.month_of(core.today()))
    due = {}
    for ch in core.open_charges():
        due[ch["family_id"]] = due.get(ch["family_id"], 0) + ch["due"]
    kids = {}
    for s in q("SELECT family_id, first_name FROM students WHERE status='active' ORDER BY joined_at, id"):
        kids.setdefault(s["family_id"], []).append(s["first_name"])
    return [{"id": f["id"], "name": f["name"], "parent_name": f["parent_name"], "parent_phone": f["parent_phone"],
             "children": kids.get(f["id"], []), "due": due.get(f["id"], 0)}
            for f in q("SELECT * FROM families WHERE status='active' ORDER BY name")]


@route("GET", r"/api/families/(\d+)", STAFF)
def family_detail(c, fid):
    core.ensure_charges(core.month_of(core.today()))
    return family_payload(int(fid))


@route("PATCH", r"/api/families/(\d+)", STAFF)
def family_update(c, fid):
    fam = family_payload(int(fid))
    b = c.body
    run("""UPDATE families SET name=?, parent_name=?, parent_gender=?, parent_phone=?, parent2_name=?, parent2_phone=?, note=?
           WHERE id=?""", text(b, "name", required=True), text(b, "parent_name", required=True),
        choice(b.get("parent_gender") or fam["parent_gender"], ("m", "f"), "родитель"),
        text(b, "parent_phone", required=True), text(b, "parent2_name"), text(b, "parent2_phone"),
        text(b, "note", maxlen=1000), fam["id"])
    audit(c, "Изменены контакты семьи", fam["name"])
    return {"ok": True}


@route("GET", "/api/finance/debtors", STAFF)
def debtors(c):
    cur = core.month_of(core.today())
    core.ensure_charges(cur)
    fams = {}
    for ch in core.open_charges():
        f = fams.get(ch["family_id"])
        if not f:
            fam = one("SELECT * FROM families WHERE id=?", ch["family_id"])
            rem = one("SELECT created_at FROM reminders WHERE family_id=? ORDER BY id DESC LIMIT 1", fam["id"])
            f = fams[ch["family_id"]] = {"family_id": fam["id"], "name": fam["name"], "parent_name": fam["parent_name"],
                                         "parent_phone": fam["parent_phone"], "due": 0, "overdue": 0, "months": [],
                                         "children": [], "last_reminder": rem["created_at"] if rem else None}
        f["due"] += ch["due"]
        if ch["month"] < cur:
            f["overdue"] += ch["due"]
        if ch["month_label"] not in f["months"]:
            f["months"].append(ch["month_label"])
        if ch["first_name"] not in f["children"]:
            f["children"].append(ch["first_name"])
    out = sorted(fams.values(), key=lambda f: (-f["overdue"], -f["due"]))
    return {"month_label": core.month_label(cur), "due_day": int(core.setting("due_day")),
            "total": sum(f["due"] for f in out), "overdue": sum(f["overdue"] for f in out), "families": out}


@route("GET", "/api/finance/payments", STAFF)
def payments_list(c):
    month = c.arg("month") or core.month_of(core.today())
    if not re.match(r"^\d{4}-\d\d$", month):
        raise ApiError(422, "Неверный месяц")
    first, last = core.month_bounds(month)
    rows = q("""SELECT p.id, p.amount, p.method, p.paid_at, p.status, p.cancel_reason, p.family_id, ch.month,
                       s.first_name, s.last_name, g.name group_name, f.name family_name, u.name by_name
                FROM payments p JOIN charges ch ON ch.id = p.charge_id JOIN students s ON s.id = p.student_id
                JOIN groups g ON g.id = ch.group_id JOIN families f ON f.id = p.family_id
                LEFT JOIN users u ON u.id = p.created_by
                WHERE p.paid_at BETWEEN ? AND ? ORDER BY p.paid_at DESC, p.id DESC""", first.isoformat(), last.isoformat())
    for r in rows:
        r["student"] = r.pop("first_name") + " " + r.pop("last_name")
        r["month_label"] = core.month_label(r["month"])
    active = [r for r in rows if r["status"] == "active"]
    by_method = {}
    for r in active:
        by_method[r["method"]] = by_method.get(r["method"], 0) + r["amount"]
    return {"month": month, "month_label": core.month_label(month), "prev": core.add_months(month, -1),
            "next": core.add_months(month, 1) if month < core.month_of(core.today()) else None,
            "total": sum(r["amount"] for r in active), "by_method": by_method, "payments": rows}


@route("POST", "/api/finance/payments", STAFF)
def payment_create(c):
    b = c.body
    fam = one("SELECT * FROM families WHERE id=?", integer(b.get("family_id"), "семья"))
    if not fam:
        raise ApiError(404, "Семья не найдена")
    method = choice(b.get("method") or "cash", METHODS, "способ оплаты")
    paid_at = date_of(b.get("paid_at") or core.today().isoformat(), "дата оплаты")
    if paid_at > core.today():
        raise ApiError(422, "Дата оплаты не может быть в будущем")
    items = b.get("items") or []
    if not items:
        raise ApiError(422, "Выберите, за что принимается оплата")
    opened = {ch["id"]: ch for ch in core.open_charges(family_id=fam["id"])}
    batch = secrets.token_hex(4)
    total, seen = 0, set()
    for it in items:
        cid = integer(it.get("charge_id"), "начисление")
        ch = opened.get(cid)
        if not ch or cid in seen:
            raise ApiError(422, "Начисление уже оплачено или относится к другой семье")
        seen.add(cid)
        amount = integer(it.get("amount"), "сумма", 1)
        if amount > ch["due"]:
            raise ApiError(422, "Сумма больше остатка: %s, %s — осталось %s" % (ch["first_name"], ch["month_label"], core.money(ch["due"])))
        run("""INSERT INTO payments (charge_id, family_id, student_id, amount, method, paid_at, batch, comment, created_by)
               VALUES (?,?,?,?,?,?,?,?,?)""", cid, fam["id"], ch["student_id"], amount, method, paid_at.isoformat(), batch,
            text(b, "comment"), c.user["id"])
        total += amount
    audit(c, "Принята оплата", "%s — %s" % (fam["name"], core.money(total)))
    left = sum(ch["due"] for ch in core.open_charges(family_id=fam["id"]))
    return {"ok": True, "total": total, "left": left}


@route("POST", r"/api/finance/payments/(\d+)/cancel", STAFF)
def payment_cancel(c, pid):
    p = one("SELECT p.*, f.name family_name FROM payments p JOIN families f ON f.id = p.family_id WHERE p.id=?", int(pid))
    if not p or p["status"] != "active":
        raise ApiError(404, "Платёж не найден или уже отменён")
    run("UPDATE payments SET status='cancelled', cancel_reason=? WHERE id=?", text(c.body, "reason", required=True), p["id"])
    audit(c, "Платёж отменён", "%s — %s: %s" % (p["family_name"], core.money(p["amount"]), text(c.body, "reason")))
    return {"ok": True}


@route("POST", "/api/finance/reminders", STAFF)
def reminder_create(c):
    fam = family_payload(integer(c.body.get("family_id"), "семья"))
    if not fam["open"]:
        raise ApiError(422, "У этой семьи нет долга")
    school = core.setting("school_name")
    first = fam["parent_name"].split(" ")[0]
    hello = "уважаемый" if fam["parent_gender"] == "m" else "уважаемая"
    me_first = c.user["name"].split(" ")[0]
    lines = ["Ассаляму алейкум, %s %s!" % (hello, first), "",
             "Пишет %s, %s (%s). Позвольте мягко напомнить об оплате занятий:" % (me_first, ROLE_LABEL[c.user["role"]], school), ""]
    self_pay = len(fam["children"]) == 1 and fam["children"][0]["name"] == fam["parent_name"]
    rows, order = {}, []
    for ch in fam["open"]:  # одна строка на ребёнка и группу, месяцы — через точку с запятой
        key = (ch["student_id"], ch["group_id"])
        if key not in rows:
            who = "" if self_pay else ch["student"].split(" ")[0] + ", "
            note = " (со скидкой %d%%)" % ch["discount_pct"] if ch["discount_pct"] else ""
            rows[key] = ["• %s«%s»%s: " % (who, ch["group_name"], note), []]
            order.append(key)
        rows[key][1].append("%s — %s%s" % (ch["month_label"].split(" ")[0], core.money(ch["due"]), " (остаток)" if ch["paid"] else ""))
    for key in order:
        lines.append(rows[key][0] + "; ".join(rows[key][1]))
    lines += ["", "Итого к оплате: %s." % core.money(fam["due"]), "",
              "Если вы уже оплатили — пожалуйста, не обращайте внимания на это сообщение. "
              "Если сейчас непросто с оплатой — напишите нам, обязательно найдём решение.", "",
              "Джазакумуллаху хайран! Пусть Аллах благословит вашу семью."]
    body = "\n".join(lines)
    run("INSERT INTO reminders (family_id, amount, text, created_by, created_at) VALUES (?,?,?,?,?)",
        fam["id"], fam["due"], body, c.user["id"], core.now())
    audit(c, "Подготовлено напоминание", "%s — %s" % (fam["name"], core.money(fam["due"])))
    return {"text": body, "phone": fam["parent_phone"], "parent_name": fam["parent_name"], "due": fam["due"]}


# ---------- зарплата (только владелец) ----------
@route("GET", "/api/salaries", OWNER)
def salaries(c):
    month = c.arg("month") or core.month_of(core.today())
    if not re.match(r"^\d{4}-\d\d$", month):
        raise ApiError(422, "Неверный месяц")
    rows = core.salary_report(month)
    cur = core.month_of(core.today())
    return {"month": month, "month_label": core.month_label(month), "is_current": month == cur,
            "prev": core.add_months(month, -1), "next": core.add_months(month, 1) if month < cur else None,
            "accrued": sum(r["accrued"] for r in rows), "paid": sum(r["paid"] for r in rows),
            "due": sum(r["due"] for r in rows), "teachers": rows}


@route("POST", "/api/salaries/payouts", OWNER)
def payout_create(c):
    month = str(c.body.get("month") or "")
    if not re.match(r"^\d{4}-\d\d$", month):
        raise ApiError(422, "Неверный месяц")
    tid = integer(c.body.get("teacher_id"), "учитель")
    row = next((r for r in core.salary_report(month) if r["teacher_id"] == tid), None)
    if not row:
        raise ApiError(404, "Учитель не найден")
    amount = integer(c.body.get("amount"), "сумма", 1)
    if amount > row["due"]:
        raise ApiError(422, "Сумма больше начисленного остатка (%s)" % core.money(row["due"]))
    run("INSERT INTO payouts (teacher_id, month, amount, paid_at, note, created_by) VALUES (?,?,?,?,?,?)",
        tid, month, amount, core.today().isoformat(), text(c.body, "note"), c.user["id"])
    audit(c, "Выплата учителю", "%s, %s — %s" % (row["name"], core.month_label(month), core.money(amount)))
    return {"ok": True}


@route("POST", r"/api/salaries/payouts/(\d+)/cancel", OWNER)
def payout_cancel(c, pid):
    p = one("SELECT p.*, t.name FROM payouts p JOIN teachers t ON t.id = p.teacher_id WHERE p.id=? AND p.status='active'", int(pid))
    if not p:
        raise ApiError(404, "Выплата не найдена")
    run("UPDATE payouts SET status='cancelled' WHERE id=?", p["id"])
    audit(c, "Выплата отменена", "%s — %s" % (p["name"], core.money(p["amount"])))
    return {"ok": True}


# ---------- учителя ----------
@route("GET", "/api/teachers", STAFF)
def teachers_list(c):
    out = []
    for t in q("SELECT * FROM teachers ORDER BY status, name"):
        item = {"id": t["id"], "name": t["name"], "gender": t["gender"], "phone": t["phone"], "status": t["status"],
                "groups": [g["name"] for g in q("SELECT name FROM groups WHERE teacher_id=? AND status='active' ORDER BY name", t["id"])],
                "students": val("""SELECT COUNT(DISTINCT e.student_id) FROM enrollments e JOIN groups g ON g.id = e.group_id
                                   WHERE g.teacher_id=? AND e.status='active'""", t["id"]),
                "login": val("SELECT login FROM users WHERE teacher_id=? AND status='active'", t["id"])}
        if c.user["role"] == "owner":
            item.update(pay_type=t["pay_type"], pay_value=t["pay_value"])
        out.append(item)
    return out


def teacher_fields(c):
    b = c.body
    pay_type = choice(b.get("pay_type") or "per_lesson", ("per_lesson", "percent"), "схема оплаты")
    return (text(b, "name", required=True), choice(b.get("gender"), ("m", "f"), "пол"), text(b, "phone"), pay_type,
            integer(b.get("pay_value") or 0, "ставка", 0, 100 if pay_type == "percent" else 1000000))


@route("POST", "/api/teachers", OWNER)
def teacher_create(c):
    name, gender, phone, pay_type, pay_value = teacher_fields(c)
    login_name = text(c.body, "login").lower()
    password = str(c.body.get("password") or "")
    if login_name:
        if not re.match(r"^[a-z0-9_.-]{3,30}$", login_name):
            raise ApiError(422, "Логин: латинские буквы и цифры, от 3 символов")
        if val("SELECT 1 FROM users WHERE login=?", login_name):
            raise ApiError(422, "Такой логин уже занят")
        if len(password) < 8:
            raise ApiError(422, "Пароль — не короче 8 символов")
    tid = run("INSERT INTO teachers (name, gender, phone, pay_type, pay_value, hired_at) VALUES (?,?,?,?,?,?)",
              name, gender, phone, pay_type, pay_value, core.today().isoformat())
    if login_name:
        run("INSERT INTO users (login, name, role, pass_hash, teacher_id) VALUES (?,?,'teacher',?,?)",
            login_name, name, core.hash_password(password), tid)
    audit(c, "Добавлен учитель", name)
    return {"id": tid}


@route("PATCH", r"/api/teachers/(\d+)", OWNER)
def teacher_update(c, tid):
    t = one("SELECT * FROM teachers WHERE id=?", int(tid))
    if not t:
        raise ApiError(404, "Учитель не найден")
    if "status" in c.body:
        status = choice(c.body["status"], ("active", "archived"), "статус")
        if status == "archived" and val("SELECT COUNT(*) FROM groups WHERE teacher_id=? AND status='active'", t["id"]):
            raise ApiError(422, "У учителя есть действующие группы. Сначала передайте их другому учителю.")
        run("UPDATE teachers SET status=? WHERE id=?", status, t["id"])
        run("UPDATE users SET status=? WHERE teacher_id=?", status, t["id"])
        if status == "archived":
            run("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE teacher_id=?)", t["id"])
        audit(c, "Учитель в архиве" if status == "archived" else "Учитель возвращён из архива", t["name"])
        return {"ok": True}
    name, gender, phone, pay_type, pay_value = teacher_fields(c)
    run("UPDATE teachers SET name=?, gender=?, phone=?, pay_type=?, pay_value=? WHERE id=?",
        name, gender, phone, pay_type, pay_value, t["id"])
    run("UPDATE users SET name=? WHERE teacher_id=?", name, t["id"])
    audit(c, "Изменены данные учителя", name)
    return {"ok": True}


# ---------- заявки ----------
@route("GET", "/api/applications", STAFF)
def applications_list(c):
    rows = q("""SELECT a.*, d.name direction FROM applications a LEFT JOIN directions d ON d.id = a.direction_id
                ORDER BY a.created_at DESC""")
    for a in rows:
        a["age"] = core.age(a["birth_date"])
        a["name"] = "%s %s" % (a["child_first"], a["child_last"])
    return rows


@route("POST", "/api/applications", STAFF)
def application_create(c):
    b = c.body
    birth = date_of(b.get("birth_date"), "дата рождения", required=False)
    ts = core.now()
    aid = run("""INSERT INTO applications (child_first, child_last, gender, birth_date, parent_name, parent_gender, phone,
                 direction_id, source, note, stage, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?, 'new', ?, ?)""",
              text(b, "child_first", required=True), text(b, "child_last", required=True),
              choice(b.get("gender"), ("m", "f"), "пол"), birth.isoformat() if birth else None,
              text(b, "parent_name", required=True), choice(b.get("parent_gender") or "f", ("m", "f"), "родитель"),
              text(b, "phone", required=True), integer(b["direction_id"], "направление") if b.get("direction_id") else None,
              text(b, "source"), text(b, "note", maxlen=1000), ts, ts)
    audit(c, "Новая заявка", "%s %s" % (text(b, "child_first"), text(b, "child_last")))
    return {"id": aid}


@route("PATCH", r"/api/applications/(\d+)", STAFF)
def application_update(c, aid):
    a = one("SELECT * FROM applications WHERE id=?", int(aid))
    if not a:
        raise ApiError(404, "Заявка не найдена")
    stage = choice(c.body.get("stage"), ("new", "contacted", "trial", "declined"), "этап")
    if a["stage"] == "enrolled":
        raise ApiError(422, "Заявка уже закрыта зачислением")
    note = text(c.body, "note", maxlen=1000) if "note" in c.body else a["note"]
    run("UPDATE applications SET stage=?, note=?, updated_at=? WHERE id=?", stage, note, core.now(), a["id"])
    audit(c, "Заявка: этап изменён", "%s %s → %s" % (a["child_first"], a["child_last"], stage))
    return {"ok": True}


@route("POST", r"/api/applications/(\d+)/enroll", STAFF)
def application_enroll(c, aid):
    """Заявка → ученик: создаёт семью (или находит по телефону), ученика и запись в группу одним действием."""
    a = one("SELECT * FROM applications WHERE id=?", int(aid))
    if not a:
        raise ApiError(404, "Заявка не найдена")
    if a["stage"] in ("enrolled", "declined"):
        raise ApiError(422, "Заявка уже закрыта")
    gid = integer(c.body.get("group_id"), "группа")
    check_enroll({"gender": a["gender"]}, gid)  # проверка до любых изменений
    fid, created = find_or_create_family(c, {"parent_name": a["parent_name"], "parent_phone": a["phone"],
                                             "parent_gender": a["parent_gender"]}, a["child_last"])
    sid = run("INSERT INTO students (family_id, first_name, last_name, gender, birth_date, joined_at) VALUES (?,?,?,?,?,?)",
              fid, a["child_first"], a["child_last"], a["gender"], a["birth_date"], core.today().isoformat())
    do_enroll(c, one("SELECT * FROM students WHERE id=?", sid), gid)
    run("UPDATE applications SET stage='enrolled', student_id=?, updated_at=? WHERE id=?", sid, core.now(), a["id"])
    audit(c, "Заявка → зачислен", "%s %s" % (a["child_first"], a["child_last"]))
    return {"student_id": sid, "family_id": fid, "family_created": created}


# ---------- настройки и журнал ----------
@route("GET", "/api/settings", OWNER)
def settings_get(c):
    return {k: core.setting(k) for k in core.DEFAULT_SETTINGS}


@route("PATCH", "/api/settings", OWNER)
def settings_set(c):
    b = c.body
    vals = {"school_name": text(b, "school_name", required=True), "currency": text(b, "currency", maxlen=5) or "₽",
            "discount2": str(integer(b.get("discount2"), "скидка второму ребёнку", 0, 100)),
            "discount3": str(integer(b.get("discount3"), "скидка третьему ребёнку", 0, 100)),
            "due_day": str(integer(b.get("due_day"), "день оплаты", 1, 28))}
    for k, v in vals.items():
        run("INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT (key) DO UPDATE SET value = excluded.value", k, v)
    audit(c, "Изменены настройки школы", "")
    return {"ok": True}


@route("GET", "/api/audit", OWNER)
def audit_list(c):
    return q("SELECT user_name, action, details, at FROM audit ORDER BY id DESC LIMIT 150")


# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        if os.environ.get("LOG"):
            sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_PATCH(self):
        self.dispatch("PATCH")

    def send_body(self, status, body, ctype, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, data, cookie=None):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_body(status, body, "application/json; charset=utf-8", {"Set-Cookie": cookie} if cookie else None)

    def current_user(self):
        m = re.search(r"(?:^|;\s*)sid=([\w-]+)", self.headers.get("Cookie") or "")
        if not m:
            return None
        u = one("""SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
                   WHERE s.token=? AND s.expires_at > ? AND u.status='active'""", m.group(1), core.now())
        if u:
            u["_token"] = m.group(1)
        return u

    def read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 1000000:
            raise ApiError(413, "Слишком большой запрос")
        raw = self.rfile.read(n) if n else b""
        if not raw:
            return {}
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            raise ApiError(415, "Ожидается JSON")
        try:
            data = json.loads(raw.decode("utf-8"))
        except ValueError:
            raise ApiError(400, "Неверный JSON")
        if not isinstance(data, dict):
            raise ApiError(400, "Неверный JSON")
        return data

    def dispatch(self, method):
        url = urlparse(self.path)
        if not url.path.startswith("/api/"):
            return self.static(url.path) if method == "GET" else self.send_json(405, {"error": "Метод не поддерживается"})
        with db.LOCK:
            try:
                body = self.read_body() if method != "GET" else {}
                user = self.current_user()
                for m, rx, roles, fn in ROUTES:
                    match = rx.match(url.path) if m == method else None
                    if not match:
                        continue
                    if roles is not PUBLIC:
                        if not user:
                            raise ApiError(401, "Войдите в систему")
                        if user["role"] not in roles:
                            raise ApiError(403, "Недостаточно прав для этого действия")
                    c = Ctx(user, body, parse_qs(url.query))
                    result = fn(c, *match.groups())
                    db.conn().commit()
                    return self.send_json(200, result, c.set_cookie)
                raise ApiError(404, "Не найдено")
            except ApiError as e:
                db.conn().rollback()
                self.send_json(e.status, {"error": e.message})
            except Exception:
                db.conn().rollback()
                traceback.print_exc()
                self.send_json(500, {"error": "Внутренняя ошибка сервера"})

    def static(self, path):
        rel = "index.html" if path in ("/", "/index.html") else path[len("/static/"):] if path.startswith("/static/") else None
        full_path = os.path.realpath(os.path.join(STATIC, rel)) if rel else None
        if not full_path or not full_path.startswith(os.path.realpath(STATIC) + os.sep) or not os.path.isfile(full_path):
            return self.send_body(404, "Не найдено".encode("utf-8"), "text/plain; charset=utf-8")
        ctype = mimetypes.guess_type(full_path)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
            ctype += "; charset=utf-8"
        with open(full_path, "rb") as f:
            self.send_body(200, f.read(), ctype)


def main():
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8420"))
    with db.LOCK:
        fresh = seed.ensure_seeded()
        core.ensure_charges(core.month_of(core.today()))
        db.conn().commit()
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    print("Школа Корана запущена: http://localhost:%d" % port)
    if host == "0.0.0.0":
        try:
            import socket
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            probe.connect(("10.255.255.255", 1))  # пакеты не отправляются, только узнаём свой адрес в сети
            print("С телефона в той же сети Wi-Fi: http://%s:%d" % (probe.getsockname()[0], port))
            probe.close()
        except OSError:
            pass
    print("База данных: %s%s" % (db.DB_PATH, " (созданы демо-данные)" if fresh else ""))
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено")


if __name__ == "__main__":
    main()
