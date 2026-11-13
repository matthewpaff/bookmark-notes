"""Portable exports through the actual local HTTP server."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from bookmark_notes.server import make_server
from bookmark_notes.store import BookmarkStore


class ExportTests(unittest.TestCase):
    def test_export_is_complete_utf8_and_does_not_change_the_library(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bookmarks.sqlite3'
            server = make_server(path, port=0)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            def request(route):
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                try:
                    connection.request('GET', route)
                    response = connection.getresponse()
                    return response.status, response.getheader('Content-Type'), response.read()
                finally:
                    connection.close()
            try:
                status, content_type, raw = request('/export')
                self.assertEqual(status, 200)
                empty = json.loads(raw.decode('utf-8'))
                self.assertEqual(empty, {'schema': 'bookmark-notes.export.v1', 'bookmarks': []})
                expected = []
                with BookmarkStore(path) as store:
                    for index in range(14):
                        expected.append(store.save(f'\u8bb0\u5f55 {index}', f'https://example.com/export-{index}',
                                                   notes='Caf\u00e9 notes', tags='reference,python'))
                before = path.read_bytes()
                status, content_type, raw = request('/export?q=absent&page=99')
                self.assertEqual(status, 200)
                self.assertEqual(content_type, 'application/json; charset=utf-8')
                self.assertEqual(json.loads(raw.decode('utf-8'))['bookmarks'], expected)
                self.assertEqual(path.read_bytes(), before)
            finally:
                server.shutdown()
                worker.join(timeout=5)
                server.server_close()
