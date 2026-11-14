"""Storage and routing for short links."""
import os
import sqlite3
import string
import time

ALPHABET = string.digits + string.ascii_letters
SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
    code       TEXT PRIMARY KEY,
    url        TEXT NOT NULL,
    created_at REAL NOT NULL,
    hits       INTEGER NOT NULL DEFAULT 0,
    last_hit   REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS links_url ON links (url);
"""


def encode_id(value, width=6):
    """Encode an integer into a fixed-width base62 string using a stable alphabet."""
    if value < 0:
        raise ValueError("negative id")
    digits = []
    while value:
        value, rem = divmod(value, len(ALPHABET))
        digits.append(ALPHABET[rem])
    text = "".join(reversed(digits)) or ALPHABET[0]
    return text.rjust(width, ALPHABET[0])


def resolve_path(path):
    """Map a request path to (kind, value)."""
    path = path.split("?", 1)[0]
    if path in ("/health", "/healthz"):
        return "health", ""
    if path == "/api/links":
        return "api", "links"
    if path == "/":
        return "home", ""
    code = path.lstrip("/")
    if code and all(ch in ALPHABET for ch in code) and 3 <= len(code) <= 12:
        return "redirect", code
    return "not_found", path


class Shortener:
    def __init__(self, path="links.db", clock=time.time):
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript(SCHEMA)
        self.db.commit()
        self.clock = clock

    def close(self):
        self.db.close()

    def shorten(self, url):
        if not url or "://" not in url:
            raise ValueError("url must be absolute")
        row = self.db.execute("SELECT code FROM links WHERE url=?", (url,)).fetchone()
        if row:
            return row[0]
        cursor = self.db.execute(
            "INSERT INTO links (code, url, created_at) VALUES (?, ?, ?)",
            ("pending-" + str(self.clock()), url, self.clock()))
        rowid = cursor.lastrowid
        code = encode_id(rowid)
        self.db.execute("UPDATE links SET code=? WHERE rowid=?", (code, rowid))
        self.db.commit()
        return code

    def resolve(self, code):
        row = self.db.execute("SELECT url FROM links WHERE code=?", (code,)).fetchone()
        return row[0] if row else None

    def hit(self, code):
        url = self.resolve(code)
        if url:
            self.db.execute("UPDATE links SET hits=hits+1, last_hit=? WHERE code=?",
                            (self.clock(), code))
            self.db.commit()
        return url

    def stats(self, code):
        row = self.db.execute(
            "SELECT url, hits, created_at, last_hit FROM links WHERE code=?", (code,)).fetchone()
        if not row:
            return None
        return {"code": code, "url": row[0], "hits": row[1],
                "created_at": row[2], "last_hit": row[3]}

    def top(self, limit=10):
        rows = self.db.execute(
            "SELECT code, url, hits FROM links ORDER BY hits DESC, created_at DESC LIMIT ?",
            (limit,)).fetchall()
        return [{"code": c, "url": u, "hits": h} for c, u, h in rows]
