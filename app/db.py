import json, sqlite3
from datetime import datetime, timezone
from .config import DATABASE_PATH

def connect():
    con = sqlite3.connect(DATABASE_PATH, timeout=15, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with connect() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS alerts (
          id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
          symbol TEXT NOT NULL, kind TEXT NOT NULL, message TEXT NOT NULL, payload TEXT NOT NULL)''')
        con.execute('''CREATE TABLE IF NOT EXISTS news (
          id INTEGER PRIMARY KEY AUTOINCREMENT, published_at TEXT, title TEXT NOT NULL,
          link TEXT NOT NULL UNIQUE, source TEXT NOT NULL, summary TEXT)''')
        con.execute('''CREATE TABLE IF NOT EXISTS alert_dedup (
          dedupe_key TEXT PRIMARY KEY, alert_id INTEGER NOT NULL, created_at TEXT NOT NULL)''')

def save_alert(symbol, kind, message, payload, dedupe_key=None):
    """Save alert once. Returns (alert_id, created) so notifications are also deduped."""
    with connect() as con:
        if dedupe_key:
            existing = con.execute("SELECT alert_id FROM alert_dedup WHERE dedupe_key=?", (dedupe_key,)).fetchone()
            if existing:
                return int(existing["alert_id"]), False
        cur = con.execute("INSERT INTO alerts(created_at,symbol,kind,message,payload) VALUES(?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), symbol, kind, message, json.dumps(payload)))
        alert_id = int(cur.lastrowid)
        if dedupe_key:
            con.execute("INSERT OR IGNORE INTO alert_dedup(dedupe_key,alert_id,created_at) VALUES(?,?,?)",
                (dedupe_key, alert_id, datetime.now(timezone.utc).isoformat()))
        return alert_id, True

def get_alerts(limit=100):
    with connect() as con:
        return [dict(r) for r in con.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

def save_news(items):
    with connect() as con:
        for x in items:
            try:
                con.execute("INSERT OR IGNORE INTO news(published_at,title,link,source,summary) VALUES(?,?,?,?,?)",
                  (x.get("published_at"), x["title"], x["link"], x.get("source","RSS"), x.get("summary","")))
            except Exception:
                pass

def get_news(limit=100):
    with connect() as con:
        return [dict(r) for r in con.execute("SELECT * FROM news ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
