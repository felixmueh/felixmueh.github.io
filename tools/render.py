#!/usr/bin/env python3
"""Render the generated parts of the site from Felix's CV data.

    python3 tools/render.py

Input:   data/cv.yaml: a git-ignored symlink into the Bewerbung repo
         (cv/data/), see README.md "Content from cv.yaml".
Outputs: index.html  the project rows, between
                     <!-- BEGIN generated: projects --> and <!-- END generated: projects -->,
                     and the "More projects" list, between
                     <!-- BEGIN generated: more-projects --> and <!-- END generated: more-projects -->
Everything outside the markers stays hand-written and is left alone.

The CV data is the single source for the PDF CV and this site
(docs/cv-decisions.md "Website" in the Bewerbung repo). Project rows come
from the `web:` blocks of its entries (schema: cv/README.md there), in
English.

Deliberately not rendered: the CV itself. The site had an HTML CV page
(cv.html) generated here until 25.11.2026; Felix replaced it with links to
the PDF CVs in German and English (files/), which are built in the
Bewerbung repo and copied here by hand.

Privacy: cv.yaml's `person` holds address, phone, private e-mail and date
of birth, and GitHub Pages publishes everything committed. This script
takes nothing from `person` at all (name, GitHub and LinkedIn would be
allowed, but the page headers that show them are hand-written).
tools/tests/test_render.py checks that no private `person` value reaches
any page.

No fallback (Felix's rule): if the data is missing or malformed, the
script stops with a message and writes nothing. There is no cached copy.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import jinja2
import yaml
from markupsafe import Markup

ROOT = Path(__file__).resolve().parent.parent  # the site repo
DATA = ROOT / "data"
LANG = "en"                 # the site is English only for now


class RenderError(Exception):
    pass


# ==============================================================================
# Loading the data
# ==============================================================================
# Both files are symlinks into the Bewerbung repo. A dangling or missing link
# is the likely failure on a new machine, so say how to fix it.
def load(name: str):
    path = DATA / name
    if not path.exists():
        raise RenderError(
            f"{path.relative_to(ROOT)} is missing (or a broken symlink). It must link to "
            f"the Bewerbung repo's cv/data/{name}; see README.md, \"Content from cv.yaml\".")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise RenderError(f"invalid YAML in {path.relative_to(ROOT)}: {e}")


def pick(value, where: str, required: bool = True) -> str:
    """A text value from cv.yaml: plain string or {de, en}. English only; no German fallback."""
    if value is None:
        if required:
            raise RenderError(f"{where}: missing text")
        return ""
    if isinstance(value, (str, int, float)):
        return str(value)
    if isinstance(value, dict) and value.get(LANG) is not None:
        return str(value[LANG])
    raise RenderError(f"{where}: no '{LANG}' text")


# ==============================================================================
# Inline markup → HTML
# ==============================================================================
# The same inline markup as the CV generator (cv/README.md "Text values"):
# **bold**, *italic*, [text](url), [[placeholder]], and a newline for a line
# break. The Bewerbung generator's parser (cv/tools/build.py, tex()) emits
# LaTeX and lives in another repo, so this is a small self-contained HTML
# version of it instead of an import across repos. The pattern is copied from
# build.py's _MARKUP; if the markup there grows, grow it here too. One
# difference: a placeholder may span lines here (clip stand-ins use "\n").
MARKUP = re.compile(
    r"\[\[(?P<ph>.+?)\]\]"                         # [[placeholder]]
    r"|\[(?P<ltext>[^\]]+)\]\((?P<url>[^)\s]+)\)"   # [text](url)
    r"|\*\*(?P<bold>.+?)\*\*"                      # **bold**
    r"|\*(?P<ital>[^*]+?)\*",                      # *italic*
    re.S,
)


def todo_comment(text: str) -> str:
    # tools/check_todos.sh lists "TODO(felix): …" up to the first ">", and an
    # HTML comment must not contain "--"; keep the note on one line.
    note = " · ".join(part.strip() for part in text.splitlines())
    return f"<!-- TODO(felix): {note.replace('--', '–').replace('>', '›')} -->"


def placeholder(text: str) -> str | None:
    """The text inside [[…]] if the whole value is one placeholder, else None."""
    m = re.fullmatch(r"\s*\[\[(.+)\]\]\s*", text, re.S)
    return m.group(1) if m else None


def to_html(text: str) -> Markup:
    """Convert a text value (language already picked) to HTML; everything else is escaped."""
    text = text.strip()
    out, pos = [], 0
    for m in MARKUP.finditer(text):
        out.append(html.escape(text[pos:m.start()], quote=False))
        if m.group("ph"):
            # Marked twice, like every placeholder on the site (README.md):
            # the comment for check_todos.sh, the class for the red marking.
            out.append(todo_comment(m.group("ph")) + f'<span class="todo">{to_html(m.group("ph"))}</span>')
        elif m.group("url"):
            out.append(f'<a href="{html.escape(m.group("url"))}">{to_html(m.group("ltext"))}</a>')
        elif m.group("bold"):
            out.append(f"<strong>{to_html(m.group('bold'))}</strong>")
        else:
            out.append(f"<em>{to_html(m.group('ital'))}</em>")
        pos = m.end()
    out.append(html.escape(text[pos:], quote=False))
    return Markup("".join(out).replace("\n", "<br>"))


# ==============================================================================
# Project rows (index.html)
# ==============================================================================
# One row per entry with a `web:` block, by `web.order`. The markup is the
# hand-written rows' (style.css: .row, .row.key, .ph, .clip, .meta, .links).
# `reviewed` is Felix's approval marker (Bewerbung cv/README.md, "reviewed");
# it is accepted here and not rendered.
#
# `section` splits the rows into two lists (Felix, 25.11.2026): like on
# jonbarron.info every row of the main list has a picture, and projects
# without a useful one go to the compact text-only "More projects" list
# below it. Each list is sorted by `order`, which stays unique across both.
WEB_KEYS = {"order", "highlight", "title", "meta", "tech", "summary", "clip", "still", "page",
            "links", "reviewed", "section"}
SECTIONS = ("main", "more")


def row_media(web: dict, where: str) -> dict | None:
    """The media slot of a row: a real clip (with the still as its poster),
    a real still, a [[placeholder]] stand-in, or None (an empty slot).

    Paths are relative to this repo. The media are made by separate agents
    and may not exist yet when a row already names them, so a named file
    that is missing is left out with a warning instead of failing the
    render: the row then shows the still, or an empty slot. That isn't a
    fallback to a weaker source; it is the same empty slot a row without
    media has, and the warning says what is missing.
    """
    clip, still = web.get("clip"), web.get("still")
    for kind, src in (("clip", clip), ("still", still)):
        if src and placeholder(src) is not None:
            ph = placeholder(src)
            return {"kind": kind, "placeholder": True, "comment": Markup(todo_comment(ph)),
                    "text": to_html(ph)}

    def present(src):
        if src and not (ROOT / src).is_file():
            print(f"render.py: warning: {where}: {src} doesn't exist; left out", file=sys.stderr)
            return None
        return src

    clip, still = present(clip), present(still)
    if clip:
        # WebM first (smaller); the MP4 next to it, if there is one, for
        # Safari versions without WebM.
        mp4 = str(Path(clip).with_suffix(".mp4"))
        sources = [{"src": clip, "type": "video/webm" if clip.endswith(".webm") else "video/mp4"}]
        if mp4 != clip and (ROOT / mp4).is_file():
            sources.append({"src": mp4, "type": "video/mp4"})
        return {"kind": "clip", "placeholder": False, "sources": sources, "poster": still}
    if still:
        return {"kind": "still", "placeholder": False, "src": still}
    return None


def project_rows(data: dict) -> list[dict]:
    rows = []
    for e in data.get("entries") or []:
        web = e.get("web")
        if web is None:
            continue
        where = f"entry {e.get('id')}.web"
        # The Bewerbung build validates web blocks too; checked again here
        # because a typo would otherwise drop a field from the site silently.
        unknown = sorted(set(web) - WEB_KEYS)
        if unknown:
            raise RenderError(f"{where}: unknown key(s) {', '.join(unknown)}")
        if not isinstance(web.get("order"), int):
            raise RenderError(f"{where}: `order` must be a number")
        section = web.get("section", "main")
        if section not in SECTIONS:
            raise RenderError(f"{where}.section: must be one of {', '.join(SECTIONS)}, not {section!r}")
        # The "More projects" list has no picture column and no highlight, so
        # these would vanish from the site without a word (the Bewerbung build
        # rejects them too).
        if section == "more":
            unshown = [k for k in ("clip", "still", "highlight") if web.get(k)]
            if unshown:
                raise RenderError(f"{where}: {', '.join(unshown)} not shown in \"More projects\" "
                                  f"(section: more)")

        media = row_media(web, where) if section == "main" else None

        # Links: "project page" first when there is a page, then the listed
        # ones. A link without url is shown as text (usually a placeholder).
        links = []
        if web.get("page"):
            links.append({"url": web["page"], "comment": "", "label": Markup("project page"), "todo": False})
        for i, link in enumerate(web.get("links") or []):
            label = pick(link.get("label"), f"{where}.links[{i}].label")
            ph = placeholder(label)
            links.append({
                "url": link.get("url"),
                "todo": ph is not None,
                "comment": Markup(todo_comment(ph)) if ph is not None else "",
                "label": to_html(ph if ph is not None else label),
            })

        # The title links to the project page, else to the first real link.
        title_url = web.get("page") or next((l["url"] for l in links if l["url"]), None)
        rows.append({
            "order": web["order"],
            "section": section,
            "highlight": bool(web.get("highlight")),
            "title": to_html(pick(web.get("title") or e.get("title"), f"{where}.title")),
            "title_url": title_url,
            "meta": to_html(pick(web.get("meta"), f"{where}.meta", required=False)),
            "tech": [str(label) for label in web.get("tech") or []],
            "summary": to_html(pick(web.get("summary"), f"{where}.summary", required=False)),
            "media": media,
            "links": links,
        })
    orders = [r["order"] for r in rows]
    if len(orders) != len(set(orders)):
        raise RenderError(f"web.order used twice: {sorted(orders)}")
    return sorted(rows, key=lambda r: r["order"])


def split_sections(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """The rows of the main list and of "More projects", each still in `order`."""
    return ([r for r in rows if r["section"] == "main"],
            [r for r in rows if r["section"] == "more"])


ROWS_TEMPLATE = """\
{% for r in rows %}
    <article class="row{{ ' key' if r.highlight }}">
{%- if r.media and r.media.placeholder %}
      {{ r.media.comment }}
      <div class="ph{{ ' clip' if r.media.kind == 'clip' }} todo">{{ r.media.text }}</div>
{%- elif r.media and r.media.kind == 'clip' %}
      <div class="clip"><video loop muted playsinline preload="metadata"{% if r.media.poster %} poster="{{ r.media.poster }}"{% endif %} aria-label="Clip: {{ r.title|striptags }}">
{%- for s in r.media.sources %}<source src="{{ s.src }}" type="{{ s.type }}">{% endfor %}</video></div>
{%- elif r.media %}
      <div class="still"><img src="{{ r.media.src }}" alt="{{ r.title|striptags }}"></div>
{%- else %}
      <div></div>
{%- endif %}
      <div>
        <h3>{% if r.title_url %}<a href="{{ r.title_url }}">{{ r.title }}</a>{% else %}{{ r.title }}{% endif %}</h3>
{%- if r.meta %}
        <div class="meta">{{ r.meta }}</div>
{%- endif %}
{%- if r.tech %}
        <ul class="tech" aria-label="Languages and tools">{% for label in r.tech %}<li>{{ label }}</li>{% endfor %}</ul>
{%- endif %}
{%- if r.links %}
        <div class="links">
{%- for l in r.links %}
          {% if l.comment %}{{ l.comment }}{% endif %}{% if l.url %}<a href="{{ l.url }}"{{ ' class="todo"'|safe if l.todo }}>{{ l.label }}</a>{% else %}<span{{ ' class="todo"'|safe if l.todo }}>{{ l.label }}</span>{% endif %}
{%- endfor %}
        </div>
{%- endif %}
{%- if r.summary %}
        <p>{{ r.summary }}</p>
{%- endif %}
      </div>
    </article>
{%- endfor %}
"""


# "More projects": one compact entry per row, no picture column. The meta
# line takes the tech labels as plain text, so an entry stays three short
# lines: title and meta, summary, links. Empty list → no heading either.
MORE_TEMPLATE = """\
{% if rows %}
  <h2 id="more-projects">More projects</h2>
  <ul class="more-projects">
{%- for r in rows %}
    <li>
      <h3>{% if r.title_url %}<a href="{{ r.title_url }}">{{ r.title }}</a>{% else %}{{ r.title }}{% endif %}</h3>
{%- if r.meta or r.tech %}
      <div class="meta">{{ r.meta }}{% if r.meta and r.tech %} · {% endif %}{{ r.tech|join(', ') }}</div>
{%- endif %}
{%- if r.summary %}
      <p>{{ r.summary }}</p>
{%- endif %}
{%- if r.links %}
      <div class="links">
{%- for l in r.links %}
        {% if l.comment %}{{ l.comment }}{% endif %}{% if l.url %}<a href="{{ l.url }}"{{ ' class="todo"'|safe if l.todo }}>{{ l.label }}</a>{% else %}<span{{ ' class="todo"'|safe if l.todo }}>{{ l.label }}</span>{% endif %}
{%- endfor %}
      </div>
{%- endif %}
    </li>
{%- endfor %}
  </ul>
{%- endif %}
"""


# ==============================================================================
# Writing between the markers
# ==============================================================================
GENERATED_NOTE = ("<!-- Generated by tools/render.py from data/cv.yaml (the Bewerbung repo's "
                  "cv/data/cv.yaml). Don't edit here: edit cv.yaml and run the script. -->")


def splice(page: str, name: str, body: str) -> str:
    """Replace what is between the BEGIN/END markers named `name` in page."""
    begin, end = f"<!-- BEGIN generated: {name} -->", f"<!-- END generated: {name} -->"
    if page.count(begin) != 1 or page.count(end) != 1 or page.index(begin) > page.index(end):
        raise RenderError(f"expected exactly one {begin} … {end} pair")
    head, rest = page.split(begin)
    _, tail = rest.split(end)
    indent = re.search(r"[ \t]*$", head).group(0)
    return f"{head}{begin}\n{indent}{GENERATED_NOTE}{body.rstrip()}\n{indent}{end}{tail}"


def main() -> int:
    try:
        data = load("cv.yaml")
        env = jinja2.Environment(autoescape=True, keep_trailing_newline=True)
        main_rows, more_rows = split_sections(project_rows(data))
        rows = env.from_string(ROWS_TEMPLATE).render(rows=main_rows)
        more = env.from_string(MORE_TEMPLATE).render(rows=more_rows)
        # Splice both lists before writing, so an error leaves the page untouched.
        index = splice((ROOT / "index.html").read_text(encoding="utf-8"), "projects", rows)
        index = splice(index, "more-projects", more)
    except RenderError as e:
        print(f"render.py: {e}", file=sys.stderr)
        return 1
    (ROOT / "index.html").write_text(index, encoding="utf-8")
    print("rendered: index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
