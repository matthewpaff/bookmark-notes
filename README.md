# Bookmark Notes

A small original bookmark-and-notes library for one person on one computer.
Save links, add context and tags, search, and return to useful things later.
The responsive interface works without JavaScript; `/` optionally focuses search.

**Python 3.10+ with SQLite support is the only requirement.** No third-party
packages, environment setup, frontend build, or external services are needed.

## Run

From this repository directory:

```console
python -m bookmark_notes
```

Open **http://127.0.0.1:18765** in your browser. Stop with Ctrl+C in the terminal.
Bookmarks persist in `~/.bookmark-notes/bookmarks.sqlite3`.

```console
python -m bookmark_notes --db demo.sqlite3 --port 18766
python -m bookmark_notes --help
```

Use a separate file for a demo. Starting a new database does not add sample data.
Help does not create a database. An invalid or occupied port reports an error.

## Use

Choose **Export JSON** to download the entire library, including titles, URLs, notes, tags, IDs, and saved timestamps. Exports use the versioned `bookmark-notes.export.v1` schema and UTF-8, independent of the current search or page. Empty libraries export an empty `bookmarks` array. This is a portable data export; automatic importing or restoration is not implemented. The export stays on your computer and does not change saved bookmarks.

1. Select **Add bookmark**, enter a title and an HTTP/HTTPS URL, and save.
2. Add optional notes and comma-separated tags such as `python, reference`.
3. Search the title, URL, or notes. Select a tag to combine it with search.
4. Select **Edit** on a card to update its details.
5. To delete, open Edit, check the confirmation box, and select Delete bookmark.

Search is literal and case-insensitive for ASCII letters. SQL syntax and `%` are
ordinary text. Newest bookmarks appear first, with 12 per page. Tags are normalized
to lowercase and deduplicated; each accepts 1–30 ASCII letters, digits, or hyphens,
with up to 12 tags per bookmark. Titles allow 200 characters, notes 4000, and URLs
2048. An exact duplicate URL is rejected; URLs are not otherwise canonicalized.

Links open in a new tab without sending the referrer or exposing the library tab.
The application does not download saved pages, favicons, or remote metadata.
Invalid form submissions retain the entered values and show a useful error.

## Scope and data

The server binds only to **127.0.0.1**. It is a local learning application without
accounts, authentication, or TLS; do not expose it through a proxy, tunnel, or
public interface. It uses Python's small standard-library HTTP server rather than
a production application server.

Forms use a per-process CSRF token, allowed-host checks, and POST/redirect/GET.
User content is escaped, queries are parameterized, and writes are transactional.
A restrictive content-security policy loads only local scripts and styles.

Restarting expires open forms; reload them before saving. Data is stored unencrypted
in SQLite. To back up the library, stop the application and copy its database file.
Search and tags describe your saved links; there is no page-content search, syncing,
browser extension, import/export, or automatic URL-health check.

## Development

```console
python -m unittest discover -s tests -v
```

Tests use temporary databases and an ephemeral loopback port. They cover persistence,
validation, duplicate links, tags, search, pagination, rollback, escaping, assets,
form submission, request protections, and confirmed deletion. They do not contact
external websites or need a browser installation.

`store.py` owns data validation and SQL; `views.py` renders escaped HTML;
`server.py` handles requests; `static/` contains CSS and the optional keyboard shortcut.
See [CONTRIBUTING.md](CONTRIBUTING.md) and the [MIT license](LICENSE).

[History and provenance](HISTORY.md).
