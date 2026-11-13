"""Escaped, server-rendered pages with progressive enhancement."""
from html import escape
from urllib.parse import urlencode


def e(value):
    return escape(str(value), quote=True)


def link(**params):
    return "/?" + urlencode({key: value for key, value in params.items() if value})


def layout(title, content, sidebar=""):
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} · Bookmark Notes</title><link rel="stylesheet" href="/static/app.css">
<script src="/static/app.js" defer></script></head><body>
<a class="skip" href="#main">Skip to content</a>
<header class="topbar"><a class="brand" href="/"><span class="brand-icon" aria-hidden="true">b.</span>
Bookmark Notes</a><a href="/export" download="bookmarks.json">Export JSON</a><span class="local-badge">YOUR LOCAL LIBRARY</span></header>
<div class="workspace"><aside class="sidebar"><p class="eyebrow">WORKSPACE</p>
<a class="library-link" href="/">All bookmarks <span aria-hidden="true">↗</span></a>
{sidebar}<div class="sidebar-note">A small place for useful things.<br>Saved on this computer.</div></aside>
<main id="main">{content}</main></div><footer>Bookmark Notes <span>Python + SQLite · Personal, by design</span></footer>
</body></html>'''


def library(result, tags, query="", tag=""):
    tag_links = '<p class="eyebrow tag-heading">TAGS</p><nav aria-label="Filter by tag">'
    for item in tags:
        current = ' aria-current="page"' if item["name"] == tag else ""
        tag_links += f'<a class="tag-link" href="{e(link(q=query, tag=item["name"]))}"{current}># {e(item["name"])} <span>{item["count"]}</span></a>'
    tag_links += '</nav>' if tags else '<p class="muted">Tags appear when you save a bookmark.</p></nav>'
    count = result["total"]
    cards = ""
    for item in result["items"]:
        chips = "".join(f'<a class="chip" href="{e(link(q=query, tag=name))}">{e(name)}</a>' for name in item["tags"])
        notes = e(item["notes"]) if item["notes"] else '<span class="muted">No notes yet.</span>'
        cards += f'''<article class="bookmark-card"><div class="card-top"><span class="card-icon" aria-hidden="true">↗</span>
<a class="edit-link" href="/edit?id={item["id"]}" aria-label="Edit {e(item["title"])}">Edit</a></div>
<h2><a href="{e(item["url"])}" target="_blank" rel="noopener noreferrer">{e(item["title"])}</a></h2>
<p class="url">{e(item["url"])}</p><p class="notes">{notes}</p><div class="chips">{chips}</div>
<div class="card-date">Saved {e(item["created_at"][:10])}</div></article>'''
    if not cards:
        cards = '''<div class="empty"><span class="empty-icon" aria-hidden="true">＋</span>
<h2>No bookmarks here yet</h2><p>Save a useful link, or try a different search.</p>
<a class="button primary" href="/new">Add a bookmark</a></div>'''
    pagination = ""
    if result["pages"] > 1:
        pagination = '<nav class="pagination" aria-label="Results pages">'
        if result["page"] > 1:
            pagination += f'<a class="button" href="{e(link(q=query, tag=tag, page=result["page"] - 1))}">Previous</a>'
        pagination += f'<span>Page {result["page"]} of {result["pages"]}</span>'
        if result["page"] < result["pages"]:
            pagination += f'<a class="button" href="{e(link(q=query, tag=tag, page=result["page"] + 1))}">Next</a>'
        pagination += '</nav>'
    filter_note = f'<p class="filter-note">Tag: <strong>{e(tag)}</strong> · <a href="{e(link(q=query))}">Clear tag</a></p>' if tag else ""
    content = f'''<div class="page-heading"><div><p class="eyebrow">KEEP WHAT MATTERS</p>
<h1>Your link library<span class="accent">.</span></h1><p class="intro">Good reads, helpful tools, and ideas worth keeping.</p></div>
<a class="button primary" href="/new">＋ Add bookmark</a></div>
<form class="search-bar" method="get" action="/" role="search"><label class="sr-only" for="search">Search title, URL, or notes</label>
<input id="search" type="search" name="q" value="{e(query)}" placeholder="Search title, URL, or notes…" maxlength="200">
<input type="hidden" name="tag" value="{e(tag)}"><button class="button" type="submit">Search</button></form>
<div class="results-heading"><p role="status">{count} bookmark{"s" if count != 1 else ""}{" found" if query or tag else " saved"}</p>
<span class="keyboard-hint">Press <kbd>/</kbd> to search</span></div>{filter_note}
<div class="card-grid">{cards}</div>{pagination}'''
    return layout("Library", content, tag_links)


def editor(token, item=None, error=""):
    item = item or {"title": "", "url": "", "notes": "", "tags": ""}
    bookmark_id = item.get("id", "")
    tags = ", ".join(item["tags"]) if isinstance(item["tags"], list) else item["tags"]
    heading = "Edit bookmark" if bookmark_id else "Save something useful"
    error_html = f'<div class="error" role="alert">{e(error)}</div>' if error else ""
    delete = f'''<form class="delete-form" method="post" action="/delete">
<input type="hidden" name="csrf" value="{e(token)}"><input type="hidden" name="id" value="{e(bookmark_id)}">
<label class="confirm"><input type="checkbox" name="confirm" value="yes" required> I want to permanently delete this bookmark.</label>
<button class="button danger" type="submit">Delete bookmark</button></form>''' if bookmark_id else ""
    content = f'''<a class="back-link" href="/">← Back to library</a><p class="eyebrow">A PLACE TO COME BACK TO</p>
<h1>{heading}<span class="accent">.</span></h1><p class="intro">A link, a little context, and a tag or two.</p>{error_html}
<form class="editor" method="post" action="/save"><input type="hidden" name="csrf" value="{e(token)}">
<input type="hidden" name="id" value="{e(bookmark_id)}">
<label for="title">Title</label><input id="title" name="title" value="{e(item["title"])}" maxlength="200" required autofocus>
<label for="url">URL</label><input id="url" name="url" type="url" value="{e(item["url"])}" maxlength="2048" placeholder="https://example.com" required>
<label for="notes">Notes <span class="optional">optional</span></label><textarea id="notes" name="notes" rows="5" maxlength="4000">{e(item["notes"])}</textarea>
<label for="tags">Tags <span class="optional">optional</span></label><input id="tags" name="tags" value="{e(tags)}" maxlength="400" aria-describedby="tag-help" placeholder="python, reference, reading">
<p id="tag-help" class="field-help">Separate with commas. Up to 12 tags; letters, numbers, and hyphens.</p>
<div class="form-actions"><button class="button primary" type="submit">Save bookmark</button><a class="button" href="/">Cancel</a></div>
</form>{delete}'''
    return layout(heading, content)


def error_page(message):
    return layout("Something needs attention", f'<h1>Something needs attention.</h1><p role="alert">{e(message)}</p><a class="button" href="/">Back to library</a>')
