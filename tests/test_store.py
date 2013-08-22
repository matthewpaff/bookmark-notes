from pathlib import Path
import sqlite3
import tempfile
import unittest

from bookmark_notes.store import BookmarkStore
from bookmark_notes import views


class BookmarkTests(unittest.TestCase):
    def setUp(self):
        self.store = BookmarkStore(":memory:")
        self.addCleanup(self.store.db.close)

    def test_persistence_and_tag_normalization(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "nested" / "bookmarks.sqlite3"
            with BookmarkStore(path) as store:
                row = store.save(" Python ", "https://python.org/", " Notes ", "Python, reference, python")
            with BookmarkStore(path) as store:
                self.assertEqual(store.get(row["id"])["tags"], ["python", "reference"])
                self.assertEqual(store.get(row["id"])["notes"], "Notes")
                self.assertEqual(store.tag_counts()[0], {"name": "python", "count": 1})

    def test_invalid_urls_titles_and_tags(self):
        for url in ("javascript:alert(1)", "file:///tmp/a", "https://", "https://user:pass@example.com/",
                    "https://example.com:0", "https://example.com:99999", "https://example.com/a b",
                    "https://example.com/\nattack", "https://example.com\\@evil.test"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.store.save("Title", url)
        with self.assertRaises(ValueError):
            self.store.save(" ", "https://example.com")
        with self.assertRaises(ValueError):
            self.store.save("Title", "https://example.com", tags="bad tag")

    def test_duplicate_url_and_atomic_edit(self):
        first = self.store.save("One", "https://example.com/1", tags="old")
        self.store.save("Two", "https://example.com/2")
        with self.assertRaises(ValueError):
            self.store.save("Changed", "https://example.com/2", tags="new", bookmark_id=first["id"])
        self.assertEqual(self.store.get(first["id"]), first)
        edited = self.store.save("Changed", first["url"], tags="new", bookmark_id=first["id"])
        self.assertEqual(edited["tags"], ["new"])
        self.assertEqual(edited["created_at"], first["created_at"])

    def test_search_is_literal_and_combines_with_tags(self):
        self.store.save("100% Python", "https://example.com/a", "SQLite notes", "python,reading")
        self.store.save("Other", "https://example.com/b", "Python notes", "web")
        self.assertEqual(self.store.find("%", "python")["total"], 1)
        self.assertEqual(self.store.find("SQLITE")["total"], 1)
        self.assertEqual(self.store.find("python", "web")["total"], 1)
        self.assertEqual(self.store.find("' OR 1=1 --")["total"], 0)

    def test_pagination_is_stable_and_clamps_last_page(self):
        for number in range(14):
            self.store.save(str(number), "https://example.com/" + str(number))
        first, last = self.store.find(), self.store.find(page=99)
        self.assertEqual((first["total"], first["pages"], len(first["items"])), (14, 2, 12))
        self.assertEqual((last["page"], len(last["items"])), (2, 2))
        self.assertFalse(set(row["id"] for row in first["items"]) & set(row["id"] for row in last["items"]))

    def test_delete_cascades_tags_and_missing_id_fails(self):
        row = self.store.save("One", "https://example.com/", tags="python")
        self.store.delete(row["id"])
        self.assertEqual(self.store.tag_counts(), [])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM bookmark_tags").fetchone()[0], 0)
        with self.assertRaises(LookupError):
            self.store.get(row["id"])

    def test_failed_tag_write_rolls_back_bookmark_and_tags(self):
        row = self.store.save("Original", "https://example.com", tags="old")
        self.store.db.execute("""CREATE TRIGGER fail_tag BEFORE INSERT ON tags
            WHEN NEW.name='fail' BEGIN SELECT RAISE(ABORT, 'test'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.save("Changed", row["url"], tags="fail", bookmark_id=row["id"])
        self.assertEqual(self.store.get(row["id"]), row)

    def test_user_content_is_escaped_in_pages_and_forms(self):
        row = self.store.save('<script>alert("x")</script>', "https://example.com/?a=1&b=2",
                              '<img src=x onerror="alert(1)">', "python")
        page = views.library(self.store.find(), self.store.tag_counts(), '<svg onload="x">')
        self.assertNotIn('<script>alert(', page)
        self.assertNotIn('<img src=x', page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("a=1&amp;b=2", page)
        self.assertIn("&lt;img", views.editor("token", row))


if __name__ == "__main__":
    unittest.main()
