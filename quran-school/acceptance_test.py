#!/usr/bin/env python3
"""Приёмочные сценарии заказчика — автоматическая проверка через настоящий HTTP-сервер.

Запуск:  python3 acceptance_test.py
Поднимает отдельный сервер на временной базе с демо-данными, рабочую базу не трогает.
"""
import http.cookiejar
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("TEST_PORT", "8499"))
URL = "http://127.0.0.1:%d" % PORT
results = []


class Client(object):
    def __init__(self, login=None):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        if login:
            st, _ = self.post("/api/demo-login", {"login": login})
            assert st == 200, "демо-вход %s не удался" % login

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(URL + path, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            r = self.op.open(req, timeout=10)
            return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, {"error": raw.decode("utf-8", "replace")}

    def get(self, path):
        return self.call("GET", path)

    def post(self, path, body=None):
        return self.call("POST", path, body or {})

    def patch(self, path, body=None):
        return self.call("PATCH", path, body or {})


def scenario(title):
    def deco(fn):
        notes = []
        try:
            fn(notes.append)
            results.append((title, True, notes))
        except AssertionError as e:
            results.append((title, False, notes + ["НЕ ПРОШЛО: %s" % e]))
        except Exception as e:  # pragma: no cover
            results.append((title, False, notes + ["ОШИБКА: %r" % e]))
        return fn
    return deco


def run_all():
    owner, admin, yusuf, aisha = Client("abdullah"), Client("maryam"), Client("yusuf"), Client("aisha")
    today = owner.get("/api/me")[1]["today"]
    groups = {g["name"]: g for g in owner.get("/api/groups")[1]}
    apps = {a["name"]: a for a in owner.get("/api/applications")[1]}

    @scenario("1. Заявка превращается в ученика в группе (сценарий восстановлен по смыслу — начало ТЗ обрезано)")
    def _(note):
        a = apps["Зайд Мухаметов"]
        before = len(owner.get("/api/students")[1])
        st, r = owner.post("/api/applications/%d/enroll" % a["id"], {"group_id": groups["Алифба — мальчики"]["id"]})
        assert st == 200, r
        s = owner.get("/api/students/%d" % r["student_id"])[1]
        assert [g["name"] for g in s["groups"]] == ["Алифба — мальчики"], s["groups"]
        assert len(owner.get("/api/students")[1]) == before + 1
        assert s["charges"] and s["charges"][0]["amount"] == 3000, s["charges"]
        stage = [x for x in owner.get("/api/applications")[1] if x["id"] == a["id"]][0]["stage"]
        assert stage == "enrolled"
        note("Зайд Мухаметов зачислен в «Алифба — мальчики», начисление за месяц 3000 создано, заявка закрыта")

    @scenario("2. Пробую записать девочку в мужскую группу — система не даёт")
    def _(note):
        male = groups["Алифба — мальчики"]["id"]
        before = len(owner.get("/api/students")[1])
        st, r = owner.post("/api/applications/%d/enroll" % apps["Сумая Билалова"]["id"], {"group_id": male})
        assert st == 422 and "девочку в мужскую" in r["error"], (st, r)
        note("Заявка девочки → мужская группа: отказ «%s»" % r["error"])
        girl = [s for s in owner.get("/api/students")[1] if s["gender"] == "f"][0]
        st, r = owner.post("/api/enrollments", {"student_id": girl["id"], "group_id": male})
        assert st == 422 and "девочку" in r["error"], (st, r)
        st, r = owner.post("/api/students", {"first_name": "Тест", "last_name": "Тестова", "gender": "f",
                                             "parent_name": "Мама", "parent_phone": "+7 900 000-00-00", "group_id": male})
        assert st == 422, (st, r)
        assert len(owner.get("/api/students")[1]) == before, "при отказе не должно появляться записей"
        boy = [s for s in owner.get("/api/students")[1] if s["gender"] == "m"][0]
        st, r = owner.post("/api/enrollments", {"student_id": boy["id"], "group_id": groups["Хифз — девочки"]["id"]})
        assert st == 422, (st, r)
        note("Существующая ученица, новая ученица и мальчик в женскую группу — тоже отказ; лишних записей не создано")
        st, r = owner.post("/api/applications/%d/enroll" % apps["Сумая Билалова"]["id"], {"group_id": groups["Алифба — девочки"]["id"]})
        assert st == 200, r
        note("В женскую группу та же девочка записывается без проблем")

    @scenario("3. Учитель с телефона отмечает посещаемость своей группы меньше чем за минуту")
    def _(note):
        mine = yusuf.get("/api/groups")[1]
        gid = mine[0]["id"]
        t0 = time.time()
        st, sheet = yusuf.get("/api/attendance?group_id=%d&date=%s" % (gid, today))
        assert st == 200 and sheet["students"], sheet
        marks = {str(s["id"]): "present" for s in sheet["students"]}
        marks[str(sheet["students"][0]["id"])] = "absent"
        st, r = yusuf.post("/api/attendance", {"group_id": gid, "date": today, "marks": marks})
        assert st == 200 and r["present"] == len(marks) - 1, r
        again = yusuf.get("/api/attendance?group_id=%d&date=%s" % (gid, today))[1]
        assert again["marked"] and again["students"][0]["status"] == "absent"
        note("Группа «%s», %d учеников: 2 запроса, %.2f с на сервере. В интерфейсе это 3 нажатия: группа → отсутствующий → «Сохранить»"
             % (mine[0]["name"], len(marks), time.time() - t0))
        other = groups["Хифз — девочки"]["id"]
        st, _r = yusuf.post("/api/attendance", {"group_id": other, "date": today, "marks": {"1": "present"}})
        assert st == 403, "чужую группу отмечать нельзя"

    @scenario("4. Учитель отмечает, что ученик сдал суру, и прогресс ученика сразу меняется")
    def _(note):
        gid = [g for g in aisha.get("/api/groups")[1] if "Хифз" in g["name"]][0]["id"]
        stu = aisha.get("/api/groups/%d" % gid)[1]["students"][-1]
        before = aisha.get("/api/students/%d/hifz" % stu["id"])[1]
        nxt = [s for j in before["juz"] for s in j["surahs"] if not s["passed"]][0]
        st, after = aisha.post("/api/students/%d/hifz" % stu["id"], {"surah": nxt["n"], "passed": True, "grade": 5})
        assert st == 200, after
        assert after["summary"]["surahs"] == before["summary"]["surahs"] + 1
        assert after["summary"]["ayahs"] == before["summary"]["ayahs"] + nxt["ayahs"]
        card = aisha.get("/api/students/%d" % stu["id"])[1]["hifz"]
        assert card == after["summary"], "карточка ученика должна показывать тот же прогресс"
        note("%s: сура %d «%s» — прогресс %s%% → %s%% сразу в ответе и в карточке"
             % (stu["name"], nxt["n"], nxt["name"], before["summary"]["pct"], after["summary"]["pct"]))

    @scenario("5. Учитель не видит денег школы и чужих учеников")
    def _(note):
        for path in ("/api/finance/debtors", "/api/finance/payments", "/api/salaries", "/api/families", "/api/families/1",
                     "/api/teachers", "/api/settings", "/api/audit", "/api/applications"):
            st, _r = yusuf.get(path)
            assert st == 403, "%s отдал %s" % (path, st)
        st, _r = yusuf.post("/api/finance/payments", {"family_id": 1, "items": []})
        assert st == 403
        dash = yusuf.get("/api/dashboard")[1]
        assert "finance" not in dash and "salary_due" not in dash
        assert all("price" not in g for g in yusuf.get("/api/groups")[1])
        mine = yusuf.get("/api/students")[1]
        all_students = owner.get("/api/students")[1]
        assert 0 < len(mine) < len(all_students)
        assert all("debt" not in s and "is_free" not in s and "family_id" not in s for s in mine)
        card = yusuf.get("/api/students/%d" % mine[0]["id"])[1]
        assert "charges" not in card and "family" not in card and "is_free" not in card
        foreign = [s for s in all_students if s["id"] not in {m["id"] for m in mine}][0]
        assert yusuf.get("/api/students/%d" % foreign["id"])[0] == 403
        assert yusuf.get("/api/students/%d/hifz" % foreign["id"])[0] == 403
        assert yusuf.post("/api/students/%d/hifz" % foreign["id"], {"surah": 114})[0] == 403
        assert yusuf.get("/api/groups/%d" % groups["Хифз — девочки"]["id"])[0] == 403
        assert yusuf.patch("/api/students/%d" % mine[0]["id"], {"status": "archived", "reason": "x"})[0] == 403
        note("Сервер отдаёт 403 на оплаты, должников, зарплату, семьи, заявки, настройки; в списке %d своих учеников из %d; "
             "в ответах учителю нет цен, долгов и признака «бесплатно»" % (len(mine), len(all_students)))

    @scenario("6. Марьям вносит оплату за двоих детей одной семьи, скидка второму ребёнку считается сама")
    def _(note):
        debtors = admin.get("/api/finance/debtors")[1]["families"]
        fam = None
        for d in debtors:
            f = admin.get("/api/families/%d" % d["family_id"])[1]
            kids = {c["student_id"] for c in f["open"]}
            if len(f["children"]) == 2 and len(kids) == 2 and len(f["open"]) == 2:
                fam = f
                break
        assert fam, "в демо-данных должна быть семья с двумя детьми и неоплаченным месяцем"
        first, second = fam["open"]
        assert first["discount_pct"] == 0 and second["discount_pct"] == 20, (first, second)
        assert second["amount"] == second["base"] * 80 // 100
        total = first["due"] + second["due"]
        st, r = admin.post("/api/finance/payments", {"family_id": fam["id"], "method": "cash", "items": [
            {"charge_id": first["id"], "amount": first["due"]}, {"charge_id": second["id"], "amount": second["due"]}]})
        assert st == 200 and r["total"] == total and r["left"] == 0, r
        assert admin.get("/api/families/%d" % fam["id"])[1]["due"] == 0
        assert fam["id"] not in [d["family_id"] for d in admin.get("/api/finance/debtors")[1]["families"]]
        st, r = admin.post("/api/finance/payments", {"family_id": fam["id"], "items": [{"charge_id": first["id"], "amount": 100}]})
        assert st == 422, "повторная оплата того же начисления должна отклоняться"
        note("Семья %s: %s — %d, %s — %d (вместо %d, −20%% как второму ребёнку). Одним платежом %d, семья ушла из должников"
             % (fam["name"], first["student"], first["amount"], second["student"], second["amount"], second["base"], total))

    @scenario("7. Открываю «Кто должен», нажимаю «Напоминание» — получаю готовый вежливый текст для родителя")
    def _(note):
        d = owner.get("/api/finance/debtors")[1]
        assert d["families"], "должники должны быть"
        fam = d["families"][0]
        st, r = owner.post("/api/finance/reminders", {"family_id": fam["family_id"]})
        assert st == 200, r
        text = r["text"]
        parent_first = fam["parent_name"].split(" ")[0]
        assert parent_first in text and "Ассаляму алейкум" in text and "Итого к оплате" in text and "не обращайте внимания" in text
        assert ("{:,}".format(fam["due"]).replace(",", " ")) in text
        again = [x for x in owner.get("/api/finance/debtors")[1]["families"] if x["family_id"] == fam["family_id"]][0]
        assert again["last_reminder"], "должна появиться отметка «напоминали»"
        note("Должников: %d, всего %d. Текст для семьи %s:\n%s" % (len(d["families"]), d["total"], fam["name"],
                                                                 "\n".join("      | " + ln for ln in text.split("\n"))))

    @scenario("8. Утром открываю главный экран и за 10 секунд понимаю, как дела в школе")
    def _(note):
        t0 = time.time()
        st, d = owner.get("/api/dashboard")
        dt_ms = (time.time() - t0) * 1000
        assert st == 200
        for key in ("students", "finance", "attendance", "absent3", "applications_new", "lessons", "unmarked", "salary_due"):
            assert key in d, key
        assert d["absent3"] and d["absent3"][0]["count"] >= 3, "ученик с тремя пропусками должен быть виден"
        f = d["finance"]
        note("Один экран, один запрос (%.0f мс): учеников %d, собрано %d из %d, долг %d у %d семей, посещаемость %s%%, "
             "новых заявок %d, «%s — %d пропуска подряд», уроков сегодня %d"
             % (dt_ms, d["students"], f["collected"], f["expected"], f["debt"], f["debt_families"], d["attendance"]["week"],
                d["applications_new"], d["absent3"][0]["name"], d["absent3"][0]["count"], len(d["lessons"])))

    @scenario("9. В конце месяца вижу, сколько должен каждому учителю")
    def _(note):
        st, d = owner.get("/api/salaries")
        assert st == 200 and len(d["teachers"]) == 4, d
        assert all(t["due"] == t["accrued"] - t["paid"] for t in d["teachers"])
        assert d["due"] == sum(t["due"] for t in d["teachers"]) and d["due"] > 0
        t = [x for x in d["teachers"] if x["due"] > 0][0]
        st, r = owner.post("/api/salaries/payouts", {"teacher_id": t["teacher_id"], "month": d["month"], "amount": t["due"]})
        assert st == 200, r
        after = [x for x in owner.get("/api/salaries")[1]["teachers"] if x["teacher_id"] == t["teacher_id"]][0]
        assert after["due"] == 0
        assert admin.get("/api/salaries")[0] == 403, "зарплату видит только владелец"
        note("%s: %s" % (d["month_label"], "; ".join("%s — должен %d (начислено %d, выплачено %d)"
                                                     % (x["name"], x["due"], x["accrued"], x["paid"]) for x in d["teachers"])))
        note("После отметки выплаты долг перед «%s» = 0; администратор к зарплате не допущен (403)" % t["name"])

    @scenario("Доп. Ничего не удаляется насовсем — только архив или смена статуса")
    def _(note):
        st, _r = owner.call("DELETE", "/api/students/1")
        assert st in (404, 405, 501), "DELETE не должен поддерживаться, получили %s" % st
        s = [x for x in owner.get("/api/students")[1] if x["groups"]][0]
        st, r = owner.patch("/api/students/%d" % s["id"], {"status": "archived", "reason": "Проверка архива"})
        assert st == 200, r
        card = owner.get("/api/students/%d" % s["id"])[1]
        assert card["status"] == "archived" and card["attendance"]["marks"] and card["charges"], "история должна сохраниться"
        assert s["id"] in [x["id"] for x in owner.get("/api/students?status=archived")[1]]
        assert owner.patch("/api/students/%d" % s["id"], {"status": "active"})[0] == 200
        pay = owner.get("/api/finance/payments")[1]["payments"][0]
        assert owner.post("/api/finance/payments/%d/cancel" % pay["id"], {"reason": "Проверка отмены"})[0] == 200
        kept = [p for p in owner.get("/api/finance/payments")[1]["payments"] if p["id"] == pay["id"]][0]
        assert kept["status"] == "cancelled"
        note("Маршрутов удаления на сервере нет; ученик уходит в архив с сохранением посещений и оплат и возвращается; "
             "платёж отменяется со статусом и причиной, а не стирается")

    @scenario("Доп. Без входа данные недоступны")
    def _(note):
        anon = Client()
        for path in ("/api/students", "/api/dashboard", "/api/finance/debtors", "/api/groups"):
            assert anon.get(path)[0] == 401, path
        note("Все разделы без входа отвечают 401")


def main():
    tmp = tempfile.mkdtemp(prefix="school-test-")
    env = dict(os.environ, SCHOOL_DB=os.path.join(tmp, "test.db"), PORT=str(PORT), HOST="127.0.0.1")
    server = subprocess.Popen([sys.executable, os.path.join(BASE, "app.py")], env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(URL + "/api/public", timeout=1)
                break
            except Exception:
                time.sleep(0.1)
        else:
            raise SystemExit("Сервер не запустился")
        run_all()
    finally:
        server.terminate()
        err = server.stderr.read().decode("utf-8", "replace").strip()
    ok = sum(1 for _, passed, _ in results if passed)
    for title, passed, notes in results:
        print("%s %s" % ("✓" if passed else "✗", title))
        for n in notes:
            print("    " + n)
    print("\nИтого: %d из %d" % (ok, len(results)))
    if err:
        print("\nОшибки сервера:\n" + err)
    sys.exit(0 if ok == len(results) and not err else 1)


if __name__ == "__main__":
    main()
