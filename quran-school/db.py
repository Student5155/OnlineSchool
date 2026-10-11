"""SQLite: файл data/school.db внутри проекта."""
import os
import sqlite3
import threading

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("SCHOOL_DB", os.path.join(BASE, "data", "school.db"))
LOCK = threading.RLock()
_conn = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS teachers (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, gender TEXT NOT NULL CHECK (gender IN ('m','f')),
  phone TEXT DEFAULT '', pay_type TEXT NOT NULL DEFAULT 'per_lesson' CHECK (pay_type IN ('per_lesson','percent')),
  pay_value INTEGER NOT NULL DEFAULT 0, hired_at TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived'))
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, login TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('owner','admin','teacher')),
  pass_hash TEXT NOT NULL, teacher_id INTEGER REFERENCES teachers(id),
  is_demo INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived'))
);

CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS directions (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);

CREATE TABLE IF NOT EXISTS groups (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, direction_id INTEGER NOT NULL REFERENCES directions(id),
  gender TEXT NOT NULL CHECK (gender IN ('m','f')), teacher_id INTEGER NOT NULL REFERENCES teachers(id),
  price INTEGER NOT NULL, schedule TEXT NOT NULL DEFAULT '[]', room TEXT DEFAULT '',
  capacity INTEGER NOT NULL DEFAULT 12,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived'))
);

CREATE TABLE IF NOT EXISTS families (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, parent_name TEXT NOT NULL,
  parent_gender TEXT NOT NULL DEFAULT 'f' CHECK (parent_gender IN ('m','f')),
  parent_phone TEXT NOT NULL DEFAULT '', parent2_name TEXT DEFAULT '', parent2_phone TEXT DEFAULT '',
  note TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived'))
);

CREATE TABLE IF NOT EXISTS students (
  id INTEGER PRIMARY KEY, family_id INTEGER NOT NULL REFERENCES families(id),
  first_name TEXT NOT NULL, last_name TEXT NOT NULL,
  gender TEXT NOT NULL CHECK (gender IN ('m','f')), birth_date TEXT,
  is_free INTEGER NOT NULL DEFAULT 0, free_reason TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
  joined_at TEXT NOT NULL, archived_at TEXT, archive_reason TEXT DEFAULT '', note TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS enrollments (
  id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id),
  group_id INTEGER NOT NULL REFERENCES groups(id), start_date TEXT NOT NULL, end_date TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','ended'))
);
CREATE INDEX IF NOT EXISTS ix_enr_student ON enrollments(student_id);
CREATE INDEX IF NOT EXISTS ix_enr_group ON enrollments(group_id);

CREATE TABLE IF NOT EXISTS lessons (
  id INTEGER PRIMARY KEY, group_id INTEGER NOT NULL REFERENCES groups(id), date TEXT NOT NULL,
  teacher_id INTEGER NOT NULL REFERENCES teachers(id), marked_by INTEGER REFERENCES users(id),
  marked_at TEXT, UNIQUE (group_id, date)
);

CREATE TABLE IF NOT EXISTS attendance (
  id INTEGER PRIMARY KEY, lesson_id INTEGER NOT NULL REFERENCES lessons(id),
  student_id INTEGER NOT NULL REFERENCES students(id),
  status TEXT NOT NULL CHECK (status IN ('present','late','absent','excused')),
  UNIQUE (lesson_id, student_id)
);
CREATE INDEX IF NOT EXISTS ix_att_student ON attendance(student_id);

CREATE TABLE IF NOT EXISTS hifz (
  id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id), surah INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'passed' CHECK (status IN ('passed','revoked')),
  grade INTEGER NOT NULL DEFAULT 5, passed_at TEXT NOT NULL, teacher_id INTEGER REFERENCES teachers(id),
  marked_by INTEGER REFERENCES users(id), UNIQUE (student_id, surah)
);

CREATE TABLE IF NOT EXISTS charges (
  id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id),
  family_id INTEGER NOT NULL REFERENCES families(id), enrollment_id INTEGER NOT NULL REFERENCES enrollments(id),
  group_id INTEGER NOT NULL REFERENCES groups(id), month TEXT NOT NULL, base INTEGER NOT NULL,
  discount_pct INTEGER NOT NULL DEFAULT 0, discount_reason TEXT DEFAULT '', amount INTEGER NOT NULL,
  UNIQUE (enrollment_id, month)
);
CREATE INDEX IF NOT EXISTS ix_charge_family ON charges(family_id);

CREATE TABLE IF NOT EXISTS payments (
  id INTEGER PRIMARY KEY, charge_id INTEGER NOT NULL REFERENCES charges(id),
  family_id INTEGER NOT NULL REFERENCES families(id), student_id INTEGER NOT NULL REFERENCES students(id),
  amount INTEGER NOT NULL CHECK (amount > 0), method TEXT NOT NULL DEFAULT 'cash',
  paid_at TEXT NOT NULL, batch TEXT, comment TEXT DEFAULT '', created_by INTEGER REFERENCES users(id),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','cancelled')), cancel_reason TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_pay_charge ON payments(charge_id);

CREATE TABLE IF NOT EXISTS reminders (
  id INTEGER PRIMARY KEY, family_id INTEGER NOT NULL REFERENCES families(id), amount INTEGER NOT NULL,
  text TEXT NOT NULL, created_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payouts (
  id INTEGER PRIMARY KEY, teacher_id INTEGER NOT NULL REFERENCES teachers(id), month TEXT NOT NULL,
  amount INTEGER NOT NULL CHECK (amount > 0), paid_at TEXT NOT NULL, note TEXT DEFAULT '',
  created_by INTEGER REFERENCES users(id),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','cancelled'))
);

CREATE TABLE IF NOT EXISTS applications (
  id INTEGER PRIMARY KEY, child_first TEXT NOT NULL, child_last TEXT NOT NULL,
  gender TEXT NOT NULL CHECK (gender IN ('m','f')), birth_date TEXT,
  parent_name TEXT NOT NULL, parent_gender TEXT NOT NULL DEFAULT 'f', phone TEXT NOT NULL,
  direction_id INTEGER REFERENCES directions(id), source TEXT DEFAULT '', note TEXT DEFAULT '',
  stage TEXT NOT NULL DEFAULT 'new' CHECK (stage IN ('new','contacted','trial','enrolled','declined')),
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, student_id INTEGER REFERENCES students(id)
);

CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY, user_id INTEGER, user_name TEXT, action TEXT NOT NULL, details TEXT DEFAULT '',
  at TEXT NOT NULL
);
"""


def conn():
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA foreign_keys = ON")
        _conn.executescript(SCHEMA)
        _conn.commit()
    return _conn


def q(sql, *args):
    return [dict(r) for r in conn().execute(sql, args).fetchall()]


def one(sql, *args):
    r = conn().execute(sql, args).fetchone()
    return dict(r) if r else None


def val(sql, *args):
    r = conn().execute(sql, args).fetchone()
    return r[0] if r else None


def run(sql, *args):
    return conn().execute(sql, args).lastrowid
