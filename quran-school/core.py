"""Бизнес-правила школы: начисления, скидки, хифз, пропуски, зарплата."""
import datetime as dt
import hashlib
import hmac
import json
import secrets

from db import q, one, val, run
from quran import AYAHS, JUZ_SURAHS, TOTAL_AYAHS

MONTHS_RU = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь",
             "октябрь", "ноябрь", "декабрь"]


# ---------- даты ----------
def today():
    return dt.date.today()


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def month_of(d):
    return d.strftime("%Y-%m")


def month_bounds(month):
    y, m = map(int, month.split("-"))
    first = dt.date(y, m, 1)
    nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
    return first, nxt - dt.timedelta(days=1)


def add_months(month, n):
    y, m = map(int, month.split("-"))
    idx = y * 12 + (m - 1) + n
    return "%04d-%02d" % (idx // 12, idx % 12 + 1)


def month_label(month):
    y, m = map(int, month.split("-"))
    return "%s %d" % (MONTHS_RU[m - 1], y)


def age(birth_date, on=None):
    if not birth_date:
        return None
    b = dt.date.fromisoformat(birth_date)
    on = on or today()
    return on.year - b.year - ((on.month, on.day) < (b.month, b.day))


# ---------- пароли ----------
def hash_password(password):
    salt = secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()
    return "pbkdf2$%s$%s" % (salt, h)


def check_password(password, stored):
    try:
        _, salt, h = stored.split("$")
    except ValueError:
        return False
    calc = hashlib.pbkdf2_hmac("sha256", str(password).encode(), salt.encode(), 120000).hex()
    return hmac.compare_digest(calc, h)


# ---------- настройки ----------
DEFAULT_SETTINGS = {"school_name": "Школа Корана «Нур»", "currency": "₽", "discount2": "20",
                    "discount3": "30", "due_day": "10"}


def setting(key):
    v = val("SELECT value FROM settings WHERE key=?", key)
    return v if v is not None else DEFAULT_SETTINGS.get(key)


def money(n):
    return ("{:,}".format(int(n)).replace(",", " ")) + " " + setting("currency")


# ---------- расписание ----------
def schedule_of(group):
    try:
        return json.loads(group["schedule"] or "[]")
    except ValueError:
        return []


def lesson_time(group, date):
    for s in schedule_of(group):
        if s.get("d") == date.isoweekday():
            return s.get("t", "")
    return None


# ---------- начисления и семейная скидка ----------
def ensure_charges(month):
    """Создаёт недостающие начисления за месяц. Скидка второму и следующим детям считается здесь:
    платные дети одной семьи упорядочены по дате прихода в школу, первый платит полностью."""
    first, last = month_bounds(month)
    d2, d3 = int(setting("discount2")), int(setting("discount3"))
    rows = q("""SELECT e.id eid, e.student_id sid, e.group_id gid, g.price, s.family_id fid, s.is_free
                FROM enrollments e JOIN students s ON s.id = e.student_id JOIN groups g ON g.id = e.group_id
                WHERE e.start_date <= ? AND (e.end_date IS NULL OR e.end_date >= ?)
                ORDER BY s.joined_at, s.id""", last.isoformat(), first.isoformat())
    have = {r["enrollment_id"] for r in q("SELECT enrollment_id FROM charges WHERE month=?", month)}
    order = {}
    for r in rows:
        if not r["is_free"]:
            kids = order.setdefault(r["fid"], [])
            if r["sid"] not in kids:
                kids.append(r["sid"])
    created = 0
    for r in rows:
        if r["eid"] in have:
            continue
        if r["is_free"]:
            pct, reason = 100, "учится бесплатно"
        else:
            rank = order[r["fid"]].index(r["sid"])
            if rank == 0:
                pct, reason = 0, ""
            elif rank == 1:
                pct, reason = d2, "второй ребёнок в семье"
            else:
                pct, reason = d3, "третий ребёнок в семье" if rank == 2 else "%d-й ребёнок в семье" % (rank + 1)
        amount = int(round(r["price"] * (100 - pct) / 100.0))
        run("""INSERT INTO charges (student_id, family_id, enrollment_id, group_id, month, base,
               discount_pct, discount_reason, amount) VALUES (?,?,?,?,?,?,?,?,?)""",
            r["sid"], r["fid"], r["eid"], r["gid"], month, r["price"], pct, reason if pct else "", amount)
        created += 1
    return created


def open_charges(family_id=None, student_id=None):
    """Неоплаченные начисления по текущий месяц включительно."""
    cur = month_of(today())
    sql = """SELECT c.id, c.student_id, c.family_id, c.group_id, c.month, c.base, c.discount_pct,
                    c.discount_reason, c.amount, s.first_name, s.last_name, g.name group_name,
                    COALESCE((SELECT SUM(p.amount) FROM payments p
                              WHERE p.charge_id = c.id AND p.status = 'active'), 0) paid
             FROM charges c JOIN students s ON s.id = c.student_id JOIN groups g ON g.id = c.group_id
             WHERE c.month <= ?"""
    args = [cur]
    if family_id:
        sql += " AND c.family_id = ?"
        args.append(family_id)
    if student_id:
        sql += " AND c.student_id = ?"
        args.append(student_id)
    sql += " ORDER BY c.month, s.joined_at, s.id"
    due_day = int(setting("due_day"))
    out = []
    for r in q(sql, *args):
        r["due"] = r["amount"] - r["paid"]
        if r["due"] <= 0:
            continue
        r["overdue"] = r["month"] < cur or today().day > due_day
        r["month_label"] = month_label(r["month"])
        out.append(r)
    return out


# ---------- хифз ----------
def hifz_summary(student_id, passed=None):
    if passed is None:
        passed = {r["surah"] for r in
                  q("SELECT surah FROM hifz WHERE student_id=? AND status='passed'", student_id)}
    ayahs = sum(AYAHS[s] for s in passed)
    juz_done = [j for j in range(1, 31) if all(s in passed for s in JUZ_SURAHS[j])]
    return {"surahs": len(passed), "ayahs": ayahs, "pct": round(ayahs * 100.0 / TOTAL_AYAHS, 1),
            "juz_done": juz_done, "juz_count": len(juz_done)}


def hifz_summaries(student_ids):
    by = {sid: set() for sid in student_ids}
    for r in q("SELECT student_id, surah FROM hifz WHERE status='passed'"):
        if r["student_id"] in by:
            by[r["student_id"]].add(r["surah"])
    return {sid: hifz_summary(sid, p) for sid, p in by.items()}


# ---------- посещаемость ----------
def absent_streaks(group_ids=None, min_len=3):
    """Ученики, у которых последние min_len отмеченных уроков подряд — пропуск без причины."""
    since = (today() - dt.timedelta(days=60)).isoformat()
    rows = q("""SELECT a.student_id, l.group_id, l.date, a.status, s.first_name, s.last_name, g.name group_name
                FROM attendance a JOIN lessons l ON l.id = a.lesson_id
                JOIN enrollments e ON e.student_id = a.student_id AND e.group_id = l.group_id AND e.status = 'active'
                JOIN students s ON s.id = a.student_id AND s.status = 'active'
                JOIN groups g ON g.id = l.group_id
                WHERE l.date >= ? ORDER BY l.date DESC""", since)
    seen = {}
    for r in rows:
        if group_ids is not None and r["group_id"] not in group_ids:
            continue
        key = (r["student_id"], r["group_id"])
        st = seen.setdefault(key, {"student_id": r["student_id"], "group_id": r["group_id"],
                                   "name": r["first_name"] + " " + r["last_name"],
                                   "group_name": r["group_name"], "count": 0, "dates": [], "open": True})
        if st["open"]:
            if r["status"] == "absent":
                st["count"] += 1
                st["dates"].append(r["date"])
            else:
                st["open"] = False
    out = [dict((k, v) for k, v in st.items() if k != "open") for st in seen.values() if st["count"] >= min_len]
    out.sort(key=lambda x: -x["count"])
    return out


def attendance_rate(date_from, date_to, group_ids=None):
    sql = """SELECT a.status, COUNT(*) n FROM attendance a JOIN lessons l ON l.id = a.lesson_id
             WHERE l.date BETWEEN ? AND ?"""
    args = [date_from.isoformat(), date_to.isoformat()]
    if group_ids is not None:
        if not group_ids:
            return None
        sql += " AND l.group_id IN (%s)" % ",".join("?" * len(group_ids))
        args += list(group_ids)
    sql += " GROUP BY a.status"
    counts = {r["status"]: r["n"] for r in q(sql, *args)}
    total = sum(counts.values())
    if not total:
        return None
    return round((counts.get("present", 0) + counts.get("late", 0)) * 100.0 / total)


def student_attendance(student_ids, group_ids=None):
    """Процент посещаемости за последние 90 дней по каждому ученику."""
    since = (today() - dt.timedelta(days=90)).isoformat()
    sql = """SELECT a.student_id, a.status, COUNT(*) n FROM attendance a JOIN lessons l ON l.id = a.lesson_id
             WHERE l.date >= ?"""
    args = [since]
    if group_ids is not None:
        if not group_ids:
            return {}
        sql += " AND l.group_id IN (%s)" % ",".join("?" * len(group_ids))
        args += list(group_ids)
    sql += " GROUP BY a.student_id, a.status"
    agg = {}
    for r in q(sql, *args):
        a = agg.setdefault(r["student_id"], [0, 0])
        a[1] += r["n"]
        if r["status"] in ("present", "late"):
            a[0] += r["n"]
    ids = set(student_ids)
    return {sid: round(a[0] * 100.0 / a[1]) for sid, a in agg.items() if sid in ids and a[1]}


# ---------- зарплата учителей ----------
def salary_report(month):
    """Начислено за месяц: ставка за проведённый урок или процент от оплат, поступивших за группы учителя."""
    first, last = month_bounds(month)
    f, l = first.isoformat(), last.isoformat()
    out = []
    for t in q("SELECT * FROM teachers ORDER BY status, name"):
        lessons = val("SELECT COUNT(*) FROM lessons WHERE teacher_id=? AND date BETWEEN ? AND ?", t["id"], f, l)
        collected = val("""SELECT COALESCE(SUM(p.amount), 0) FROM payments p JOIN charges c ON c.id = p.charge_id
                           JOIN groups g ON g.id = c.group_id
                           WHERE g.teacher_id = ? AND p.status = 'active' AND p.paid_at BETWEEN ? AND ?""",
                        t["id"], f, l)
        if t["pay_type"] == "per_lesson":
            accrued = lessons * t["pay_value"]
        else:
            accrued = int(round(collected * t["pay_value"] / 100.0))
        payouts = q("""SELECT id, amount, paid_at, note FROM payouts
                       WHERE teacher_id=? AND month=? AND status='active' ORDER BY paid_at""", t["id"], month)
        paid = sum(p["amount"] for p in payouts)
        if t["status"] != "active" and not accrued and not paid:
            continue
        out.append({"teacher_id": t["id"], "name": t["name"], "pay_type": t["pay_type"],
                    "pay_value": t["pay_value"], "lessons": lessons, "collected": collected,
                    "accrued": accrued, "paid": paid, "due": accrued - paid, "payouts": payouts})
    return out
