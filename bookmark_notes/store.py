"""SQLite bookmark storage with tags and literal search."""
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit


def validate(title, url, notes, tags):
    title, url, notes = title.strip(), url.strip(), notes.strip()
    if not 1 <= len(title) <= 200:
        raise ValueError("Title must contain 1–200 characters")
    if len(url) > 2048 or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url):
        raise ValueError("URL must be at most 2048 characters with no whitespace or control characters")
    try:
        parsed = urlsplit(url)
        valid = parsed.scheme.lower() in ("http", "https") and parsed.hostname and parsed.port != 0
        if not valid or parsed.username is not None or parsed.password is not None or "\\" in url:
            raise ValueError()
    except ValueError:
        raise ValueError("Use a valid http:// or https:// URL without credentials") from None
    if len(notes) > 4000:
        raise ValueError("Notes must be at most 4000 characters")
    names = sorted(set(name.strip().lower() for name in tags.split(",") if name.strip()))
    if len(names) > 12 or any(not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,29}", name) for name in names):
        raise ValueError("Use up to 12 comma-separated tags of 1–30 ASCII letters, digits, or hyphens")
    return title, url, notes, names


class BookmarkStore:
    def __init__(self, path):
        path = str(path)
        if path != ":memory:":
            path = str(Path(path).expanduser())
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL, url TEXT NOT NULL UNIQUE, notes TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
            CREATE TABLE IF NOT EXISTS bookmark_tags (
                bookmark_id INTEGER NOT NULL REFERENCES bookmarks(id) ON DELETE CASCADE,
                tag_id INTEGER NOT NULL REFERENCES tags(id), PRIMARY KEY(bookmark_id, tag_id)
            );
            CREATE INDEX IF NOT EXISTS tags_bookmark_lookup ON bookmark_tags(tag_id, bookmark_id);
        """)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    def _with_tags(self, row):
        result = dict(row)
        result["tags"] = [tag[0] for tag in self.db.execute("""SELECT tags.name FROM tags
            JOIN bookmark_tags ON tags.id=bookmark_tags.tag_id
            WHERE bookmark_id=? ORDER BY tags.name""", (row["id"],))]
        return result

    def get(self, bookmark_id):
        row = self.db.execute("SELECT * FROM bookmarks WHERE id=?", (bookmark_id,)).fetchone()
        if row is None:
            raise LookupError("Bookmark not found")
        return self._with_tags(row)

    def save(self, title, url, notes="", tags="", bookmark_id=None):
        title, url, notes, names = validate(title, url, notes, tags)
        if bookmark_id is not None:
            self.get(bookmark_id)
        duplicate = self.db.execute("SELECT id FROM bookmarks WHERE url=?", (url,)).fetchone()
        if duplicate is not None and duplicate["id"] != bookmark_id:
            raise ValueError("That exact URL is already in your library")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.db:
            if bookmark_id is None:
                cursor = self.db.execute("""INSERT INTO bookmarks(title,url,notes,created_at,updated_at)
                    VALUES(?,?,?,?,?)""", (title, url, notes, now, now))
                bookmark_id = cursor.lastrowid
            else:
                self.db.execute("UPDATE bookmarks SET title=?,url=?,notes=?,updated_at=? WHERE id=?",
                                (title, url, notes, now, bookmark_id))
                self.db.execute("DELETE FROM bookmark_tags WHERE bookmark_id=?", (bookmark_id,))
            for name in names:
                self.db.execute("INSERT OR IGNORE INTO tags(name) VALUES(?)", (name,))
                self.db.execute("""INSERT INTO bookmark_tags(bookmark_id,tag_id)
                    SELECT ?,id FROM tags WHERE name=?""", (bookmark_id, name))
        return self.get(bookmark_id)

    def delete(self, bookmark_id):
        self.get(bookmark_id)
        with self.db:
            self.db.execute("DELETE FROM bookmarks WHERE id=?", (bookmark_id,))

    def tag_counts(self):
        return [dict(row) for row in self.db.execute("""SELECT tags.name, count(*) AS count
            FROM tags JOIN bookmark_tags ON tags.id=bookmark_tags.tag_id
            GROUP BY tags.id ORDER BY tags.name""")]

    def export(self):
        rows = self.db.execute("SELECT * FROM bookmarks ORDER BY id")
        return {"schema": "bookmark-notes.export.v1", "bookmarks": [self._with_tags(row) for row in rows]}

    def find(self, query="", tag="", page=1, page_size=12):
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError("Invalid page or page size")
        clauses, values = [], []
        if query:
            clauses.append("instr(lower(title || char(10) || url || char(10) || notes), lower(?)) > 0")
            values.append(query)
        if tag:
            clauses.append("""EXISTS(SELECT 1 FROM bookmark_tags JOIN tags ON tags.id=tag_id
                WHERE bookmark_id=bookmarks.id AND tags.name=?)""")
            values.append(tag.strip().lower())
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        total = self.db.execute("SELECT count(*) FROM bookmarks" + where, values).fetchone()[0]
        pages = max(1, (total + page_size - 1) // page_size)
        page = min(page, pages)
        rows = self.db.execute("SELECT * FROM bookmarks" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
                               (*values, page_size, (page - 1) * page_size))
        return {"items": [self._with_tags(row) for row in rows], "total": total, "page": page, "pages": pages}
