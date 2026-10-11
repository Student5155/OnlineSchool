"""Демо-данные. Запускается автоматически при первом старте, если база пустая.
Заново с нуля: python3 seed.py --reset (старая база сохраняется рядом как резервная копия)."""
import datetime as dt
import json
import os
import random
import shutil
import sys

import core
import db
from db import q, one, val, run
from quran import HIFZ_ORDER

# Демо-учётные записи. Это тестовые пароли только для показа — смените их перед настоящей работой.
DEMO_USERS = [
    {"login": "abdullah", "name": "Абдуллах Каримов", "role": "owner", "password": "demo-abdullah", "teacher": None},
    {"login": "maryam", "name": "Марьям Сафина", "role": "admin", "password": "demo-maryam", "teacher": None},
    {"login": "yusuf", "name": "Юсуф Хабибуллин", "role": "teacher", "password": "demo-yusuf", "teacher": "yusuf"},
    {"login": "aisha", "name": "Аиша Нурланова", "role": "teacher", "password": "demo-aisha", "teacher": "aisha"},
    {"login": "ibrahim", "name": "Ибрахим Галиев", "role": "teacher", "password": "demo-ibrahim", "teacher": "ibrahim"},
    {"login": "hamza", "name": "Хамза Валиев", "role": "teacher", "password": "demo-hamza", "teacher": "hamza"},
]

TEACHERS = [  # ключ, имя, пол, телефон, схема оплаты, значение
    ("yusuf", "Юсуф Хабибуллин", "m", "+7 900 555-01-01", "per_lesson", 900),
    ("ibrahim", "Ибрахим Галиев", "m", "+7 900 555-01-02", "percent", 45),
    ("hamza", "Хамза Валиев", "m", "+7 900 555-01-03", "per_lesson", 1000),
    ("aisha", "Аиша Нурланова", "f", "+7 900 555-01-04", "per_lesson", 900),
]

DIRECTIONS = ["Алифба", "Таджвид", "Хифз", "Арабский язык"]

GROUPS = [  # ключ, название, направление, пол, учитель, цена, расписание (день ISO, время), кабинет, учеников, возраст
    ("alif_m", "Алифба — мальчики", "Алифба", "m", "yusuf", 3000, [(1, "16:00"), (3, "16:00"), (6, "10:00")], "Класс 1", 9, (7, 10)),
    ("tajw_m", "Таджвид — мальчики", "Таджвид", "m", "yusuf", 3500, [(2, "16:00"), (4, "16:00"), (7, "10:00")], "Класс 1", 9, (9, 13)),
    ("hifz_m", "Хифз — мальчики", "Хифз", "m", "ibrahim", 5000, [(1, "17:30"), (2, "17:30"), (3, "17:30"), (4, "17:30")], "Класс 2", 7, (9, 13)),
    ("hifz_y", "Хифз — юноши", "Хифз", "m", "ibrahim", 5000, [(3, "19:00"), (6, "12:00"), (7, "12:00")], "Класс 2", 6, (13, 17)),
    ("arab", "Арабский язык — юноши", "Арабский язык", "m", "hamza", 3000, [(2, "18:30"), (4, "18:30")], "Класс 1", 5, (11, 16)),
    ("adult", "Таджвид — мужчины", "Таджвид", "m", "hamza", 4000, [(6, "19:00"), (7, "19:00")], "Класс 1", 6, (19, 46)),
    ("alif_f", "Алифба — девочки", "Алифба", "f", "aisha", 3000, [(1, "15:00"), (3, "15:00"), (6, "11:00")], "Женский зал", 9, (7, 11)),
    ("hifz_f", "Хифз — девочки", "Хифз", "f", "aisha", 5000, [(2, "15:00"), (4, "15:00"), (7, "11:00")], "Женский зал", 9, (10, 16)),
]

LAST = ["Ахмедов", "Исмаилов", "Юсупов", "Гайнуллин", "Закиров", "Шарипов", "Мусин", "Хасанов", "Рахимов",
        "Садыков", "Ибрагимов", "Абдуллаев", "Алиев", "Магомедов", "Латыпов", "Фаттахов", "Тагиров",
        "Хайруллин", "Насыров", "Мухаметшин", "Давлетшин", "Умаров", "Гареев", "Зарипов", "Салихов",
        "Якупов", "Байрамов", "Мансуров", "Шакиров", "Нуриев", "Камалов", "Сулейманов", "Азизов",
        "Халиков", "Миннуллин", "Вахитов", "Гатауллин", "Идрисов", "Рашидов", "Сабиров"]
BOYS = ["Ахмад", "Умар", "Али", "Хасан", "Хусейн", "Исмаил", "Мухаммад", "Билял", "Закария", "Яхья", "Иса",
        "Муса", "Харун", "Сулейман", "Дауд", "Идрис", "Салих", "Анас", "Зайд", "Усман", "Абдуррахман",
        "Тахир", "Амир", "Саид", "Малик", "Ильяс", "Юнус", "Адам", "Мустафа", "Карим", "Самир", "Халид",
        "Абубакр", "Айюб", "Амин", "Нуман"]
GIRLS = ["Фатима", "Хадиджа", "Амина", "Зайнаб", "Сафия", "Асия", "Хафса", "Сумая", "Рукая", "Ясмина", "Лейла",
         "Медина", "Салима", "Халима", "Зухра", "Малика", "Сара", "Хава", "Иман", "Нурия", "Камиля", "Самира"]
FATHERS = ["Ринат", "Ильдар", "Марат", "Рустам", "Азат", "Фарид", "Наиль", "Радик", "Булат", "Айдар", "Ильнур",
           "Шамиль", "Мурат", "Расул", "Тагир", "Дамир", "Анвар", "Рамиль"]
MOTHERS = ["Гульнара", "Лилия", "Альбина", "Диляра", "Эльвира", "Зульфия", "Алсу", "Гузель", "Ляйсан", "Мадина",
           "Айгуль", "Резеда", "Наиля", "Динара", "Зарина", "Эльмира", "Румия", "Галия"]
MEN = ["Рамиль", "Тимур", "Рашид", "Ренат", "Эмиль", "Ислам"]


def iso(d):
    return d.isoformat()


def seed():
    R = random.Random(114)
    today = core.today()
    cur = core.month_of(today)
    months = [core.add_months(cur, -2), core.add_months(cur, -1), cur]
    win_start = core.month_bounds(months[0])[0]
    phone_n = [100]

    def phone():
        phone_n[0] += 7
        n = phone_n[0]
        return "+7 900 555-%02d-%02d" % (n // 100 % 100, n % 100)

    for k, v in core.DEFAULT_SETTINGS.items():
        run("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", k, v)

    # --- учителя и пользователи ---
    T = {}
    for key, name, gender, ph, ptype, pval in TEACHERS:
        T[key] = run("INSERT INTO teachers (name, gender, phone, pay_type, pay_value, hired_at) VALUES (?,?,?,?,?,?)",
                     name, gender, ph, ptype, pval, iso(today - dt.timedelta(days=R.randint(400, 900))))
    U = {}
    for u in DEMO_USERS:
        U[u["login"]] = run("INSERT INTO users (login, name, role, pass_hash, teacher_id, is_demo) VALUES (?,?,?,?,?,1)",
                            u["login"], u["name"], u["role"], core.hash_password(u["password"]),
                            T.get(u["teacher"]))

    # --- направления и группы ---
    D = {name: run("INSERT INTO directions (name) VALUES (?)", name) for name in DIRECTIONS}
    G = {}
    for key, name, direction, gender, teacher, price, sched, room, n, ages in GROUPS:
        gid = run("""INSERT INTO groups (name, direction_id, gender, teacher_id, price, schedule, room, capacity)
                     VALUES (?,?,?,?,?,?,?,12)""", name, D[direction], gender, T[teacher], price,
                  json.dumps([{"d": d, "t": t} for d, t in sched]), room)
        G[key] = {"id": gid, "gender": gender, "teacher": T[teacher], "days": {d for d, _ in sched}, "n": n, "ages": ages}

    # --- ученики и семьи ---
    kid_slots, adult_slots = [], []
    for key, g in G.items():
        for _ in range(g["n"]):
            slot = {"g": key, "gender": g["gender"], "age": R.randint(*g["ages"])}
            (adult_slots if key == "adult" else kid_slots).append(slot)
    R.shuffle(kid_slots)
    lasts = LAST[:]
    R.shuffle(lasts)
    boys, girls = BOYS[:], GIRLS[:]
    R.shuffle(boys)
    R.shuffle(girls)

    def first_name(gender, taken):
        pool = boys if gender == "m" else girls
        for i, n in enumerate(pool):
            if n not in taken:
                pool.append(pool.pop(i))  # в конец очереди, чтобы имена реже повторялись
                return n

    def birth(age):
        return iso(dt.date(today.year - age, today.month, min(today.day, 28)) - dt.timedelta(days=R.randint(5, 330)))

    families, students = [], []  # students: dict(id, fam, slot, start, ...)

    def add_student(fam_id, first, last, slot, joined):
        sid = run("""INSERT INTO students (family_id, first_name, last_name, gender, birth_date, joined_at)
                     VALUES (?,?,?,?,?,?)""", fam_id, first, last + ("а" if slot["gender"] == "f" else ""),
                  slot["gender"], birth(slot["age"]), iso(joined))
        eid = run("INSERT INTO enrollments (student_id, group_id, start_date) VALUES (?,?,?)",
                  sid, G[slot["g"]]["id"], iso(joined))
        st = {"id": sid, "fam": fam_id, "g": slot["g"], "start": joined, "end": None, "eid": eid,
              "p_abs": R.choice([0.02, 0.03, 0.04, 0.05, 0.07, 0.1])}
        students.append(st)
        return st

    sizes = [3] * 6 + [2] * 15 + [1] * 6
    R.shuffle(sizes)
    pos = 0
    for size in sizes:
        last = lasts.pop()
        slots = kid_slots[pos:pos + size]
        pos += size
        mother_first = R.random() < 0.6
        f_name, m_name = R.choice(FATHERS) + " " + last, R.choice(MOTHERS) + " " + last + "а"
        fam_id = run("""INSERT INTO families (name, parent_name, parent_gender, parent_phone, parent2_name, parent2_phone)
                        VALUES (?,?,?,?,?,?)""", last + "ы", m_name if mother_first else f_name,
                     "f" if mother_first else "m", phone(), f_name if mother_first else m_name,
                     phone() if R.random() < 0.6 else "")
        fam = {"id": fam_id, "size": size, "kids": [], "adult": False}
        base_join = today - dt.timedelta(days=R.randint(150, 420))
        taken = set()
        for i, slot in enumerate(sorted(slots, key=lambda s: -s["age"])):
            fn = first_name(slot["gender"], taken)
            taken.add(fn)
            fam["kids"].append(add_student(fam_id, fn, last, slot, base_join + dt.timedelta(days=i * R.randint(0, 40))))
        families.append(fam)
    for slot, fn in zip(adult_slots, MEN):
        last = lasts.pop()
        fam_id = run("INSERT INTO families (name, parent_name, parent_gender, parent_phone, note) VALUES (?,?,?,?,?)",
                     fn + " " + last, fn + " " + last, "m", phone(), "Взрослый ученик, платит сам")
        fam = {"id": fam_id, "size": 1, "kids": [], "adult": True}
        fam["kids"].append(add_student(fam_id, fn, last, slot, today - dt.timedelta(days=R.randint(120, 400))))
        families.append(fam)

    by_size = lambda n: [f for f in families if f["size"] == n and not f["adult"]]
    pairs, triples, singles = by_size(2), by_size(3), by_size(1)
    adults = [f for f in families if f["adult"]]

    # двое учатся бесплатно
    for fam, reason in ((singles[2], "Сирота — решение владельца"), (singles[3], "Многодетная семья в трудной ситуации")):
        run("UPDATE students SET is_free=1, free_reason=? WHERE id=?", reason, fam["kids"][0]["id"])

    # новички: трое пришли в этом месяце, трое — в прошлом
    protected = {singles[0]["id"], singles[2]["id"], singles[3]["id"]}
    pool = [s for f in pairs[4:] + triples[2:] for s in f["kids"][-1:] if f["id"] not in protected]
    newcomers = pool[:6]
    prev_first = core.month_bounds(months[1])[0]
    for i, st in enumerate(newcomers):
        if i < 3:
            d = core.month_bounds(cur)[0] + dt.timedelta(days=min(i * 2, max(today.day - 2, 0)))
        else:
            d = prev_first + dt.timedelta(days=3 + i * 4)
        st["start"] = d
        run("UPDATE students SET joined_at=? WHERE id=?", iso(d), st["id"])
        run("UPDATE enrollments SET start_date=? WHERE id=?", iso(d), st["eid"])

    # трое хафизов дополнительно ходят на арабский
    extra = [s for s in students if s["g"] in ("hifz_m", "hifz_y") and s not in newcomers][:3]
    for st in extra:
        d = st["start"] + dt.timedelta(days=30)
        eid = run("INSERT INTO enrollments (student_id, group_id, start_date) VALUES (?,?,?)", st["id"], G["arab"]["id"], iso(d))
        students.append({"id": st["id"], "fam": st["fam"], "g": "arab", "start": d, "end": None, "eid": eid,
                         "p_abs": st["p_abs"], "extra": True})

    # двое выбывших (в архиве)
    archived = []
    for fn, slot, days_ago, reason in (("Рамазан", {"g": "alif_m", "gender": "m", "age": 9}, 22, "Семья переехала в другой город"),
                                       ("Ясмина", {"g": "alif_f", "gender": "f", "age": 8}, 48, "Перешла на занятия ближе к дому")):
        last = lasts.pop()
        fam_id = run("INSERT INTO families (name, parent_name, parent_gender, parent_phone) VALUES (?,?,?,?)",
                     last + "ы", R.choice(MOTHERS) + " " + last + "а", "f", phone())
        st = add_student(fam_id, fn, last, slot, today - dt.timedelta(days=300))
        st["end"] = today - dt.timedelta(days=days_ago)
        run("UPDATE students SET status='archived', archived_at=?, archive_reason=? WHERE id=?", iso(st["end"]), reason, st["id"])
        run("UPDATE enrollments SET status='ended', end_date=? WHERE id=?", iso(st["end"]), st["eid"])
        archived.append(st)

    # --- уроки и посещаемость за три месяца ---
    absentee = next(s for s in students if s["g"] == "tajw_m" and s not in newcomers)
    arab_days = [today - dt.timedelta(days=i) for i in range(1, 8) if (today - dt.timedelta(days=i)).isoweekday() in G["arab"]["days"]]
    skip_arab = arab_days[0] if arab_days else None  # один урок оставлен неотмеченным
    d = win_start
    while d < today:
        for key, g in G.items():
            if d.isoweekday() not in g["days"] or (key == "arab" and d == skip_arab):
                continue
            teacher_user = val("SELECT id FROM users WHERE teacher_id=?", g["teacher"])
            lid = run("INSERT INTO lessons (group_id, date, teacher_id, marked_by, marked_at) VALUES (?,?,?,?,?)",
                      g["id"], iso(d), g["teacher"], teacher_user, iso(d) + " 20:00:00")
            for st in students:
                if st["g"] != key or st["start"] > d or (st["end"] and st["end"] < d):
                    continue
                r = R.random()
                p = st["p_abs"]
                status = "absent" if r < p else "excused" if r < p + 0.03 else "late" if r < p + 0.08 else "present"
                run("INSERT INTO attendance (lesson_id, student_id, status) VALUES (?,?,?)", lid, st["id"], status)
        d += dt.timedelta(days=1)

    # один ученик с тремя пропусками подряд; у остальных случайных серий быть не должно
    for st in students:
        last3 = q("""SELECT a.id, a.status FROM attendance a JOIN lessons l ON l.id = a.lesson_id
                     WHERE a.student_id=? AND l.group_id=? ORDER BY l.date DESC LIMIT 3""", st["id"], G[st["g"]]["id"])
        if st is absentee:
            for a in last3:
                run("UPDATE attendance SET status='absent' WHERE id=?", a["id"])
        elif len(last3) == 3 and all(a["status"] == "absent" for a in last3):
            run("UPDATE attendance SET status='present' WHERE id=?", last3[0]["id"])

    # --- начисления и оплаты ---
    for m in months:
        core.ensure_charges(m)
    debt = {  # семья -> доля оплаты по месяцам (0 — не платили)
        pairs[0]["id"]: {2: 0},
        triples[0]["id"]: {1: 0, 2: 0},
        singles[0]["id"]: {0: 0, 1: 0, 2: 0},
        pairs[1]["id"]: {1: 0.5, 2: 0},
        adults[0]["id"]: {2: 0},
        singles[1]["id"]: {2: 0},
    }
    admin = U["maryam"]
    for mi, m in enumerate(months):
        first, last_day = core.month_bounds(m)
        for fam in q("SELECT DISTINCT family_id id FROM charges WHERE month=?", m):
            share = debt.get(fam["id"], {}).get(mi, 1)
            if not share:
                continue
            day = R.randint(1, 12)
            paid_at = min(first + dt.timedelta(days=day - 1), today, last_day)
            method = R.choice(["cash", "cash", "transfer", "transfer", "card"])
            batch = "%s-%d" % (m, fam["id"])
            for c in q("SELECT * FROM charges WHERE month=? AND family_id=? AND amount>0", m, fam["id"]):
                start = one("SELECT start_date FROM enrollments WHERE id=?", c["enrollment_id"])["start_date"]
                run("""INSERT INTO payments (charge_id, family_id, student_id, amount, method, paid_at, batch, created_by)
                       VALUES (?,?,?,?,?,?,?,?)""", c["id"], fam["id"], c["student_id"],
                    c["amount"] if share == 1 else int(c["amount"] * share / 100) * 100, method,
                    max(iso(paid_at), start), batch, admin)
    run("INSERT INTO reminders (family_id, amount, text, created_by, created_at) VALUES (?,?,?,?,?)",
        singles[0]["id"], 0, "Напоминание об оплате (демо-запись)", admin,
        iso(today - dt.timedelta(days=9)) + " 11:20:00")

    # --- выплаты учителям: позапрошлый месяц закрыт, в прошлом одному выплачено не всё ---
    for mi in (0, 1):
        pay_day = min(core.month_bounds(core.add_months(months[mi], 1))[0] + dt.timedelta(days=1), today)
        for row in core.salary_report(months[mi]):
            amount = row["accrued"]
            if mi == 1 and row["teacher_id"] == T["hamza"]:
                amount = int(amount * 0.6 / 100) * 100
            if amount > 0:
                run("INSERT INTO payouts (teacher_id, month, amount, paid_at, created_by) VALUES (?,?,?,?,?)",
                    row["teacher_id"], months[mi], amount, iso(pay_day), U["abdullah"])

    # --- хифз ---
    plan = {"hifz_y": [62, 52, 49, 44, 38, 31], "hifz_m": [49, 40, 38, 30, 24, 17, 11],
            "hifz_f": [51, 42, 38, 38, 28, 22, 15, 10, 6]}
    seen = set()
    for st in students:
        if st["id"] in seen or st.get("extra"):
            continue
        seen.add(st["id"])
        if st["g"] in plan and plan[st["g"]]:
            n = plan[st["g"]].pop(0)
        elif st["g"] in ("alif_m", "alif_f"):
            n = R.randint(1, 5)
        elif st["g"] == "arab":
            n = R.randint(8, 20)
        else:
            n = R.randint(4, 14)
        when = today - dt.timedelta(days=R.randint(1, 9))
        for surah in reversed(HIFZ_ORDER[:n]):
            run("INSERT INTO hifz (student_id, surah, grade, passed_at, teacher_id) VALUES (?,?,?,?,?)",
                st["id"], surah, R.choice([5, 5, 5, 4, 4, 3]), iso(when), G[st["g"]]["teacher"])
            when -= dt.timedelta(days=R.randint(4, 9))

    # --- заявки на разных этапах ---
    def app(first, last, gender, age, parent, pg, direction, source, note, stage, days_ago, student_id=None):
        ts = iso(today - dt.timedelta(days=days_ago)) + " 1%d:%02d:00" % (R.randint(0, 8), R.randint(0, 59))
        run("""INSERT INTO applications (child_first, child_last, gender, birth_date, parent_name, parent_gender, phone,
               direction_id, source, note, stage, created_at, updated_at, student_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            first, last, gender, birth(age), parent, pg, phone(), D[direction], source, note, stage, ts, ts, student_id)

    app("Сумая", "Билалова", "f", 9, "Резеда Билалова", "f", "Алифба", "Сайт", "Читает по слогам, хочет к подруге", "new", 0)
    app("Зайд", "Мухаметов", "m", 8, "Ильнур Мухаметов", "m", "Алифба", "Рекомендация", "", "new", 1)
    app("Юнус", "Давлетов", "m", 12, "Алсу Давлетова", "f", "Хифз", "Инстаграм", "Знает 30-й джуз наполовину", "new", 2)
    app("Малика", "Гареева", "f", 11, "Диляра Гареева", "f", "Хифз", "Сайт", "Перезвонить после 18:00", "contacted", 5)
    app("Адам", "Якупов", "m", 7, "Рустам Якупов", "m", "Алифба", "Мечеть", "Ждём решения родителей", "contacted", 6)
    app("Иман", "Байрамова", "f", 8, "Гузель Байрамова", "f", "Алифба", "Рекомендация", "Пробный урок в субботу", "trial", 9)
    app("Карим", "Шакиров", "m", 14, "Марат Шакиров", "m", "Арабский язык", "Сайт", "Был на пробном, понравилось", "trial", 8)
    app("Халид", "Мансуров", "m", 16, "Наиля Мансурова", "f", "Хифз", "Сайт", "Не подошло расписание", "declined", 20)
    nc = one("""SELECT s.*, f.parent_name, f.parent_gender, d.name direction FROM students s
                JOIN families f ON f.id = s.family_id JOIN enrollments e ON e.student_id = s.id
                JOIN groups g ON g.id = e.group_id JOIN directions d ON d.id = g.direction_id
                WHERE s.id=?""", newcomers[0]["id"])
    app(nc["first_name"], nc["last_name"], nc["gender"], core.age(nc["birth_date"]) or 9, nc["parent_name"],
        nc["parent_gender"], nc["direction"], "Рекомендация", "Зачислен, в школе уже учатся старшие", "enrolled", 14, nc["id"])

    run("INSERT INTO audit (user_id, user_name, action, details, at) VALUES (NULL, 'Система', 'Созданы демо-данные', ?, ?)",
        "%d учеников, %d семей" % (val("SELECT COUNT(*) FROM students"), val("SELECT COUNT(*) FROM families")), core.now())
    db.conn().commit()


def ensure_seeded():
    db.conn()
    if not val("SELECT COUNT(*) FROM users"):
        seed()
        return True
    return False


if __name__ == "__main__":
    if "--reset" in sys.argv and os.path.exists(db.DB_PATH):
        backup = db.DB_PATH + "." + dt.datetime.now().strftime("%Y%m%d-%H%M%S") + ".bak"
        shutil.move(db.DB_PATH, backup)
        print("Прежняя база сохранена:", backup)
    print("Демо-данные созданы" if ensure_seeded() else "База уже заполнена (для пересоздания: python3 seed.py --reset)")
