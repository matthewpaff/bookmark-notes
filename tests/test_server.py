import http.client
from pathlib import Path
import re
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from bookmark_notes.server import make_server


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.server = make_server(Path(cls.folder.name) / "bookmarks.sqlite3", port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.folder.cleanup()

    def request(self, method, path, data=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        final_headers = {"Content-Type": "application/x-www-form-urlencoded"} if data is not None else {}
        final_headers.update(headers or {})
        try:
            conn.request(method, path, body=urlencode(data) if data is not None else None, headers=final_headers)
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read().decode("utf-8")
        finally:
            conn.close()

    def form(self, **extra):
        return {"csrf": self.server.csrf_token, "title": "Python docs", "url": "https://docs.python.org/",
                "notes": "Useful reference", "tags": "python,reading", **extra}

    def test_full_add_search_edit_delete_workflow(self):
        status, headers, body = self.request("GET", "/new")
        self.assertEqual(status, 200)
        self.assertIn(self.server.csrf_token, body)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        status, headers, _ = self.request("POST", "/save", self.form())
        self.assertEqual((status, headers["Location"]), (303, "/"))
        status, _, body = self.request("GET", "/?q=Useful&tag=python")
        self.assertEqual(status, 200)
        self.assertIn("Python docs", body)
        bookmark_id = re.search(r'href="/edit\?id=([0-9]+)"', body).group(1)
        self.assertEqual(self.request("GET", "/edit?id=" + bookmark_id)[0], 200)
        self.assertEqual(self.request("POST", "/save", self.form(id=bookmark_id, title="Edited docs"))[0], 303)
        self.assertIn("Edited docs", self.request("GET", "/")[2])
        self.assertEqual(self.request("POST", "/delete", self.form(id=bookmark_id))[0], 400)
        self.assertEqual(self.request("POST", "/delete", self.form(id=bookmark_id, confirm="yes"))[0], 303)
        self.assertEqual(self.request("GET", "/edit?id=" + bookmark_id)[0], 404)

    def test_forged_host_and_missing_csrf_are_rejected(self):
        self.assertEqual(self.request("GET", "/", headers={"Host": "attacker.example"})[0], 403)
        self.assertEqual(self.request("POST", "/save", self.form(csrf="wrong"))[0], 403)
        self.assertEqual(self.request("POST", "/save", self.form(), headers={"Host": "attacker.example"})[0], 403)

    def test_invalid_form_preserves_escaped_values(self):
        status, _, body = self.request("POST", "/save", self.form(title='<script>alert("x")</script>', url="javascript:alert(1)"))
        self.assertEqual(status, 400)
        self.assertIn("&lt;script&gt;", body)
        self.assertNotIn('<script>alert(', body)
        self.assertIn("javascript:alert(1)", body)

    def test_assets_and_invalid_routes(self):
        status, headers, body = self.request("GET", "/static/app.css")
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("text/css"))
        self.assertIn("@media", body)
        self.assertEqual(self.request("GET", "/static/app.js")[0], 200)
        self.assertEqual(self.request("GET", "/static/../../server.py")[0], 404)
        self.assertEqual(self.request("GET", "/?page=0")[0], 400)
        self.assertEqual(self.request("GET", "/?page=not-a-number")[0], 400)
        self.assertEqual(self.request("POST", "/save", self.form(), headers={"Content-Type": "application/json"})[0], 415)


if __name__ == "__main__":
    unittest.main()
