"""Tests for tools/render.py.

Run from the repo root with any Python that has pytest, PyYAML and Jinja2:
    python3 -m pytest tools/tests

The privacy test is the important one: data/cv.yaml (a symlink into the
Bewerbung repo) holds Felix's address, phone and date of birth, and everything committed here is published. It renders with the
real data in a temporary copy of the site and checks that none of those
values reaches any page.
"""
from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SITE = Path(__file__).resolve().parents[2]

spec = importlib.util.spec_from_file_location("render", SITE / "tools" / "render.py")
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)


@pytest.fixture
def site(tmp_path) -> Path:
    """A copy of the site; data/ holds copies of the linked files, not the links
    (a relative symlink would point nowhere from the temp folder)."""
    copy = tmp_path / "site"
    # Only what render.py reads and writes: index.html, data/ and tools/
    # (the other pages come along and are checked by the privacy test too).
    # build/ and target/ hold raw recordings (GBs) and media/ the clips;
    # copying them into tmp_path (RAM-backed /tmp) once filled the tmpfs.
    # Rows whose media are missing in the copy only warn (render.row_media).
    shutil.copytree(SITE, copy, ignore=shutil.ignore_patterns(
        ".git", ".worktrees", "__pycache__", ".pytest_cache", "build", "target", "media"))
    return copy


def run_render(site: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(site / "tools" / "render.py")],
                          cwd=site, capture_output=True, text=True)


# ==============================================================================
# Privacy
# ==============================================================================
def private_values(person: dict) -> list[str]:
    """The `person` values that must never be published, with their parts.

    Not checked: name, github, linkedin (public on purpose), email (the
    hand-written headers show it on purpose, Felix 24.11.2026; render.py
    still takes nothing from `person`), subtitle (a job
    title, shown in the hand-written header), and city: "Karlsruhe" is part
    of public names ("Karlsruhe Institute of Technology") and the
    hand-written bio says it on purpose.
    """
    values = []
    for key in ("address", "phone", "birth", "photo", "signature"):
        raw = person.get(key)
        if raw is None:
            continue
        for value in (raw.values() if isinstance(raw, dict) else [raw]):
            value = str(value)
            values.append(value)
            if key == "address":
                values += [part.strip() for part in value.split(",")]   # street; postcode + city
            if key == "phone":
                values.append(re.sub(r"\D", "", value)[-8:])            # digits, any spacing
            if key == "birth":
                values += value.split(" in ")                            # date; place of birth
    return [v for v in values if v]


def test_no_private_person_field_reaches_any_page(site):
    person = yaml.safe_load((site / "data" / "cv.yaml").read_text(encoding="utf-8"))["person"]
    private = private_values(person)
    assert person.get("address") and person.get("phone"), "the real data should have an address and phone to check"

    res = run_render(site)
    assert res.returncode == 0, res.stderr

    for page in sorted(site.rglob("*.html")):
        text = page.read_text(encoding="utf-8")
        digits = re.sub(r"\D", "", text)
        for value in private:
            assert value not in text, f"{page.name} contains private data: {value!r}"
            if value.isdigit():
                assert value not in digits, f"{page.name} contains the phone number"


# The home page header links both CV PDFs. They are built in the Bewerbung
# repo (the English one from cv/jobs/_public) and copied here by hand, so
# check the copies that get published, not the builds. The German one fails
# as missing until its first copy is in files/: on purpose, the header
# already links it.
@pytest.mark.parametrize("name", ["Muehlenberend-Felix_Lebenslauf.pdf", "Muehlenberend-Felix_CV.pdf"])
def test_the_public_cv_pdfs_have_no_private_field(name):
    """pdftotext over the real file, against the real `person` values."""
    pdf = SITE / "files" / name
    assert pdf.is_file(), f"index.html links files/{name}, which is missing"
    person = yaml.safe_load((SITE / "data" / "cv.yaml").read_text(encoding="utf-8"))["person"]
    text = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True,
                          check=True).stdout
    flat = re.sub(r"\s+", " ", text.replace("\u00a0", " "))
    digits = re.sub(r"\D", "", text)

    for value in private_values(person):
        if value.isdigit():
            assert value not in digits, f"{name} contains the phone number"
        elif not value.startswith("../"):   # photo/signature paths aren't text
            assert value not in flat, f"{name} contains private data: {value!r}"
    assert person["email"] in flat and "github.com/felixmueh" in flat


# ==============================================================================
# Failure without data (no fallback)
# ==============================================================================
def test_missing_data_fails_and_writes_nothing(site):
    before = (site / "index.html").read_text(encoding="utf-8")
    (site / "data" / "cv.yaml").unlink()

    res = run_render(site)

    assert res.returncode == 1
    assert "data/cv.yaml is missing" in res.stderr
    assert (site / "index.html").read_text(encoding="utf-8") == before


# ==============================================================================
# Inline markup
# ==============================================================================
def test_markup_is_converted_and_the_rest_escaped():
    out = render.to_html("**C++** & *fast* <b> [code](https://example.org/?a=1&b=2)")
    assert out == ('<strong>C++</strong> &amp; <em>fast</em> &lt;b&gt; '
                   '<a href="https://example.org/?a=1&amp;b=2">code</a>')


def test_placeholder_gets_a_todo_comment_and_class():
    out = render.to_html("from [[start date --> ask]]")
    assert out == ('from <!-- TODO(felix): start date –› ask --><span class="todo">'
                   'start date --&gt; ask</span>')


# ==============================================================================
# Project rows: schema keys and media
# ==============================================================================
def entry(**web) -> dict:
    return {"entries": [{"id": "werk", "title": "Werk", "web": {"order": 1, **web}}]}


def test_reviewed_is_accepted_and_tech_becomes_labels():
    import datetime
    rows = render.project_rows(entry(reviewed=datetime.date(2026, 11, 24), tech=["C++", "CUDA"]))
    html_out = render.jinja2.Environment(autoescape=True).from_string(render.ROWS_TEMPLATE).render(rows=rows)
    assert '<ul class="tech" aria-label="Languages and tools"><li>C++</li><li>CUDA</li></ul>' in html_out
    assert "2026" not in html_out


def test_clip_takes_the_still_as_poster_and_the_mp4_as_second_source(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "ROOT", tmp_path)
    (tmp_path / "media" / "werk").mkdir(parents=True)
    for name in ("werk.webm", "werk.mp4", "werk.jpg"):
        (tmp_path / "media" / "werk" / name).write_bytes(b"x")

    media = render.project_rows(entry(clip="media/werk/werk.webm", still="media/werk/werk.jpg"))[0]["media"]

    assert media["poster"] == "media/werk/werk.jpg"
    assert media["sources"] == [{"src": "media/werk/werk.webm", "type": "video/webm"},
                                {"src": "media/werk/werk.mp4", "type": "video/mp4"}]


def test_missing_media_leaves_an_empty_slot_with_a_warning(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(render, "ROOT", tmp_path)

    rows = render.project_rows(entry(clip="media/werk/werk.webm", still="media/werk/werk.jpg"))

    assert rows[0]["media"] is None
    assert "media/werk/werk.webm doesn't exist" in capsys.readouterr().err


# ==============================================================================
# section: the main list or "More projects"
# ==============================================================================
def entries(*webs) -> dict:
    return {"entries": [{"id": f"werk{i}", "title": f"Werk {i}", "web": web}
                        for i, web in enumerate(webs)]}


def test_more_rows_go_to_their_own_list_each_in_order():
    rows = render.project_rows(entries(
        {"order": 4, "section": "more"}, {"order": 1}, {"order": 2, "section": "more"},
        {"order": 3, "section": "main"}))

    main, more = render.split_sections(rows)

    assert [r["order"] for r in main] == [1, 3]
    assert [r["order"] for r in more] == [2, 4]


def test_more_list_is_compact_text_with_tech_in_the_meta_line():
    rows = render.project_rows(entries({
        "order": 1, "section": "more", "meta": "Solo · 2023", "tech": ["Rust", "macros"],
        "summary": "An ECS.", "links": [{"label": "code", "url": "https://example.org/ecs"}]}))
    html_out = render.jinja2.Environment(autoescape=True).from_string(render.MORE_TEMPLATE).render(rows=rows)

    assert '<h2 id="more-projects">More projects</h2>' in html_out
    assert '<div class="meta">Solo · 2023 · Rust, macros</div>' in html_out
    assert '<a href="https://example.org/ecs">code</a>' in html_out
    assert "<img" not in html_out and "<video" not in html_out


def test_empty_more_list_renders_no_heading():
    html_out = render.jinja2.Environment(autoescape=True).from_string(render.MORE_TEMPLATE).render(rows=[])
    assert html_out.strip() == ""


def test_an_unknown_section_fails():
    with pytest.raises(render.RenderError, match="section"):
        render.project_rows(entries({"order": 1, "section": "extra"}))


def test_media_in_more_fails():
    with pytest.raises(render.RenderError, match="still"):
        render.project_rows(entries({"order": 1, "section": "more", "still": "media/werk/werk.jpg"}))
