"""Loopback-only HTTP server for a single user's local collection."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import secrets
import sqlite3
from urllib.parse import parse_qs, urlsplit

from .store import BookmarkStore
from . import views

STATIC = Path(__file__).with_name("static")


class Handler(BaseHTTPRequestHandler):
    def respond(self, body, status=200, content_type="text/html; charset=utf-8", location=None):
        body = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        if location:
            self.send_header("Location", location)
        self.end_headers()
        self.wfile.write(body)

    def allowed_host(self):
        port = self.server.server_port
        if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            self.respond(views.error_page("Use this application's localhost address."), 403)
            return False
        return True

    def do_GET(self):
        if not self.allowed_host():
            return
        try:
            route = urlsplit(self.path)
            params = parse_qs(route.query, max_num_fields=20)
            if route.path in ("/static/app.css", "/static/app.js"):
                mime = "text/css; charset=utf-8" if route.path.endswith(".css") else "text/javascript; charset=utf-8"
                self.respond((STATIC / route.path.rsplit("/", 1)[1]).read_bytes(), content_type=mime)
                return
            with BookmarkStore(self.server.db_path) as store:
                if route.path == "/":
                    query, tag = params.get("q", [""])[0], params.get("tag", [""])[0]
                    if len(query) > 200 or len(tag) > 30:
                        raise ValueError("Search or tag is too long")
                    result = store.find(query, tag, int(params.get("page", ["1"])[0]))
                    self.respond(views.library(result, store.tag_counts(), query, tag))
                elif route.path == "/new":
                    self.respond(views.editor(self.server.csrf_token))
                elif route.path == "/edit":
                    self.respond(views.editor(self.server.csrf_token, store.get(int(params.get("id", ["0"])[0]))))
                else:
                    self.respond(views.error_page("Page not found"), 404)
        except (ValueError, LookupError) as error:
            self.respond(views.error_page(str(error)), 404 if isinstance(error, LookupError) else 400)
        except (OSError, sqlite3.Error):
            self.respond(views.error_page("The local database or application files could not be accessed."), 500)

    def do_POST(self):
        if not self.allowed_host():
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/x-www-form-urlencoded":
            self.respond(views.error_page("Submit the bookmark form."), 415)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536:
                raise ValueError("Form is empty or too large")
            fields = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True, max_num_fields=20)
            if any(len(values) != 1 for values in fields.values()):
                raise ValueError("Repeated form fields are not supported")
            values = {key: val[0] for key, val in fields.items()}
            if not secrets.compare_digest(values.get("csrf", ""), self.server.csrf_token):
                self.respond(views.error_page("This form expired. Reload the page and try again."), 403)
                return
            bookmark_id = int(values["id"]) if values.get("id") else None
            if bookmark_id is not None and bookmark_id < 1:
                raise ValueError("Invalid bookmark ID")
            with BookmarkStore(self.server.db_path) as store:
                if self.path == "/save":
                    item = {key: values.get(key, "") for key in ("title", "url", "notes", "tags")}
                    item["id"] = bookmark_id or ""
                    try:
                        store.save(item["title"], item["url"], item["notes"], item["tags"], bookmark_id)
                    except ValueError as error:
                        self.respond(views.editor(self.server.csrf_token, item, str(error)), 400)
                        return
                elif self.path == "/delete":
                    if values.get("confirm") != "yes" or bookmark_id is None:
                        raise ValueError("Confirm deletion on the edit page first")
                    store.delete(bookmark_id)
                else:
                    self.respond(views.error_page("Page not found"), 404)
                    return
            self.respond("", 303, location="/")
        except (ValueError, UnicodeError, LookupError) as error:
            self.respond(views.error_page(str(error)), 404 if isinstance(error, LookupError) else 400)
        except sqlite3.Error:
            self.respond(views.error_page("The local database could not be updated."), 500)


def make_server(db_path, port=18765):
    # Database files are checked before accepting requests. Connections are short-lived.
    with BookmarkStore(db_path):
        pass
    server = HTTPServer(("127.0.0.1", port), Handler)
    server.db_path = str(db_path)
    server.csrf_token = secrets.token_urlsafe(32)
    server.timeout = 5
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run a personal, local-only bookmark library.")
    parser.add_argument("--db", default=str(Path.home() / ".bookmark-notes" / "bookmarks.sqlite3"))
    parser.add_argument("--port", type=int, default=18765)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    try:
        with make_server(args.db, args.port) as server:
            print(f"Bookmark Notes: http://127.0.0.1:{server.server_port}", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                print("\nStopped.")
        return 0
    except (OSError, sqlite3.Error) as error:
        parser.exit(1, f"error: {error}\n")
