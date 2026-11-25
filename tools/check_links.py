#!/usr/bin/env python3
"""Pre-publish check of the site's links and files.

    python3 tools/check_links.py

Over every page (*.html outside build/, target/, media/, files/, demos/ and
.git; the demos are self-contained apps with their own checks):

1. Nothing is loaded from another origin: no src, poster, srcset or
   <link> href that starts with http(s):// or //. Plain <a href> links to
   other sites are fine (README.md, "No external resources").
2. Every internal link and media path resolves to a file in the repo,
   and an #anchor exists on its target page. A path ending in "/" means
   its index.html, as GitHub Pages serves it. A path starting with "/" is
   relative to the repo root (404.html uses those).
3. media/ and files/: which files no page references (a demo may still
   use one), and the total size of both folders, since GitHub Pages
   serves the repo and its history.

Exit code 1 if 1. or 2. finds anything; 3. is a report only.
Standard library only, so it runs with any Python 3.
"""
from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"build", "target", "media", "files", "demos", ".git", ".worktrees", "data"}


class Page(HTMLParser):
    """Collects the URLs a page uses and the ids it defines."""

    def __init__(self):
        super().__init__()
        self.loads: list[str] = []   # fetched by the browser on page load
        self.links: list[str] = []   # followed only on a click
        self.ids: set[str] = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "link" and a.get("href"):
            self.loads.append(a["href"])
        for key in ("src", "poster"):
            if a.get(key):
                self.loads.append(a[key])
        if a.get("srcset"):
            self.loads += [part.split()[0] for part in a["srcset"].split(",") if part.strip()]


def pages() -> list[Path]:
    return sorted(p for p in ROOT.rglob("*.html")
                  if not SKIP_DIRS & set(p.relative_to(ROOT).parts[:-1]))


def parse(path: Path) -> Page:
    page = Page()
    page.feed(path.read_text(encoding="utf-8"))
    return page


def resolve(page: Path, url: str) -> tuple[Path, str]:
    """The file a site-internal URL points to, and its #fragment."""
    parts = urlsplit(url)
    path = unquote(parts.path)
    if path.startswith("/"):
        target = ROOT / path.lstrip("/")
    elif path:
        target = page.parent / path
    else:
        target = page          # "#anchor" on the same page
    if path.endswith("/") or target.is_dir():
        target = target / "index.html"
    return target.resolve(), parts.fragment


def is_external(url: str) -> bool:
    return url.startswith(("http://", "https://", "//"))


def main() -> int:
    errors: list[str] = []
    referenced: set[Path] = set()
    parsed = {p: parse(p) for p in pages()}

    for path, page in parsed.items():
        name = path.relative_to(ROOT)
        for url in page.loads:
            if is_external(url):
                errors.append(f"{name}: loads from another origin: {url}")
        for url in page.loads + page.links:
            if is_external(url) or url.startswith(("mailto:", "tel:", "data:")):
                continue
            target, fragment = resolve(path, url)
            referenced.add(target)
            if not target.is_file():
                errors.append(f"{name}: broken link or missing file: {url}")
                continue
            if fragment and target.suffix == ".html":
                ids = parsed[target].ids if target in parsed else parse(target).ids
                if fragment not in ids:
                    errors.append(f"{name}: no id \"{fragment}\" in {target.relative_to(ROOT)}: {url}")

    # Report: media/ and files/.
    total = 0
    unreferenced = []
    for folder in ("media", "files"):
        for f in sorted((ROOT / folder).rglob("*")):
            if f.is_file():
                total += f.stat().st_size
                if f.resolve() not in referenced:
                    unreferenced.append(f)
    print(f"media/ + files/: {total / 1e6:.1f} MB")
    if unreferenced:
        print(f"{len(unreferenced)} file(s) in media/ or files/ that no page references:")
        for f in unreferenced:
            print(f"  {f.relative_to(ROOT)}  ({f.stat().st_size / 1e6:.2f} MB)")

    if errors:
        print(f"\n{len(errors)} problem(s):")
        for e in errors:
            print(f"  {e}")
        return 1
    print("No external loads, no broken internal links.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
