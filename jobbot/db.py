"""SQLite storage: jobs, status history (events) and daily run log."""
import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from . import config

STATUSES = ["shortlisted", "needs_action", "applied", "interview", "rejected",
            "backlog", "low_match", "ignored"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fingerprint TEXT UNIQUE NOT NULL,
  url_key TEXT,
  source TEXT, external_id TEXT, title TEXT, company TEXT, location TEXT, url TEXT,
  description TEXT, posted_at TEXT, found_at TEXT,
  score INTEGER, breakdown TEXT, status TEXT, message TEXT, notes TEXT,
  applied_at TEXT, updated_at TEXT);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_url ON jobs(url_key);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER, ts TEXT, event TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, found INTEGER, fresh INTEGER, new INTEGER,
  duplicates INTEGER, shortlisted INTEGER, applied INTEGER, needs_action INTEGER, errors TEXT);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def conn():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(config.DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def init() -> None:
    with conn() as c:
        c.executescript(SCHEMA)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def keys_for(job) -> tuple[str, str]:
    """(fingerprint, url_key). Same title+company, or same URL without query string = duplicate."""
    fp = hashlib.sha1(f"{_norm(job.title)}|{_norm(job.company)}".encode()).hexdigest()
    uk = job.url.split("?")[0].split("#")[0].rstrip("/").lower()
    return fp, uk


def exists(fp: str, uk: str) -> bool:
    with conn() as c:
        return c.execute("SELECT 1 FROM jobs WHERE fingerprint=? OR url_key=?", (fp, uk)).fetchone() is not None


def insert_job(job, score: int, breakdown: dict, status: str, message: str = "", detail: str = "") -> int:
    fp, uk = keys_for(job)
    with conn() as c:
        cur = c.execute(
            """INSERT INTO jobs(fingerprint,url_key,source,external_id,title,company,location,url,description,
               posted_at,found_at,score,breakdown,status,message,notes,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fp, uk, job.source, job.external_id, job.title, job.company, job.location, job.url,
             (job.description or "")[:20000], job.posted_at, now(), score, json.dumps(breakdown),
             status, message, detail, now()))
        jid = cur.lastrowid
        c.execute("INSERT INTO events(job_id,ts,event,detail) VALUES(?,?,?,?)", (jid, now(), status, detail or "found"))
    return jid


def set_status(job_id: int, status: str, detail: str = "") -> None:
    with conn() as c:
        extra = ", applied_at=?" if status == "applied" else ""
        args = [status, now()] + ([now()] if extra else []) + [job_id]
        c.execute(f"UPDATE jobs SET status=?, updated_at=?{extra} WHERE id=?", args)
        if detail:
            c.execute("UPDATE jobs SET notes=? WHERE id=?", (detail, job_id))
        c.execute("INSERT INTO events(job_id,ts,event,detail) VALUES(?,?,?,?)", (job_id, now(), status, detail))


def set_note(job_id: int, note: str) -> None:
    with conn() as c:
        c.execute("UPDATE jobs SET notes=?, updated_at=? WHERE id=?", (note, now(), job_id))


def get_job(job_id: int) -> dict | None:
    with conn() as c:
        r = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(r) if r else None


def list_jobs(statuses: list[str] | None = None, limit: int | None = None) -> list[dict]:
    q, args = "SELECT * FROM jobs", []
    if statuses:
        q += f" WHERE status IN ({','.join('?' * len(statuses))})"
        args += statuses
    q += " ORDER BY score DESC, found_at DESC"
    if limit:
        q += f" LIMIT {int(limit)}"
    with conn() as c:
        return [dict(r) for r in c.execute(q, args)]


def stats() -> dict:
    with conn() as c:
        by = {r["status"]: r["n"] for r in c.execute("SELECT status, COUNT(*) n FROM jobs GROUP BY status")}
    total = sum(by.values())
    matching = total - by.get("low_match", 0)
    return {"total": total, "matching": matching, "by_status": by,
            "applied": by.get("applied", 0), "needs_action": by.get("needs_action", 0),
            "rejected": by.get("rejected", 0), "interview": by.get("interview", 0)}


def applied_recently(company: str, days: int) -> bool:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    with conn() as c:
        return c.execute("SELECT 1 FROM jobs WHERE lower(company)=lower(?) AND status IN ('applied','interview') "
                         "AND applied_at>=?", (company, since)).fetchone() is not None


def count_applied_today() -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with conn() as c:
        return c.execute("SELECT COUNT(*) FROM events WHERE event='applied' AND substr(ts,1,10)=?",
                         (today,)).fetchone()[0]


def events(limit: int = 300) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT e.ts, e.event, e.detail, j.title, j.company, j.url FROM events e "
            "LEFT JOIN jobs j ON j.id=e.job_id ORDER BY e.id DESC LIMIT ?", (limit,))]


def log_run(**kw) -> None:
    with conn() as c:
        c.execute("INSERT INTO runs(ts,found,fresh,new,duplicates,shortlisted,applied,needs_action,errors) "
                  "VALUES(?,?,?,?,?,?,?,?,?)",
                  (now(), kw.get("found", 0), kw.get("fresh", 0), kw.get("new", 0), kw.get("duplicates", 0),
                   kw.get("shortlisted", 0), kw.get("applied", 0), kw.get("needs_action", 0),
                   json.dumps(kw.get("errors", []))))


def runs(limit: int = 30) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,))]
