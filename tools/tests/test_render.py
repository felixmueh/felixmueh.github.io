"""Tests for tools/render.py.

Run from the repo root with any Python that has pytest, PyYAML and Jinja2:
    python3 -m pytest tools/tests

The privacy test is the important one: data/cv.yaml (a symlink into the
Bewerbung repo) holds Felix's address, phone, private e-mail and date of
birth, and everything committed here is published. It renders with the
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
    # Only what render.py reads and writes: the pages, data/ and tools/.
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

    Not checked: name, github, linkedin (public on purpose), subtitle (a job
    title, shown in the hand-written header), and city: "Karlsruhe" is part
    of public names ("Karlsruhe Institute of Technology") and the
    hand-written bio says it on purpose.
    """
    values = []
    for key in ("address", "phone", "email", "birth", "photo", "signature"):
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
    assert any("@" in v for v in private), "the real data should have a private e-mail to check"

    res = run_render(site)
    assert res.returncode == 0, res.stderr

    for page in sorted(site.rglob("*.html")):
        text = page.read_text(encoding="utf-8")
        digits = re.sub(r"\D", "", text)
        for value in private:
            assert value not in text, f"{page.name} contains private data: {value!r}"
            if value.isdigit():
                assert value not in digits, f"{page.name} contains the phone number"


def test_confidential_lines_are_skipped(site):
    data = yaml.safe_load((site / "data" / "cv.yaml").read_text(encoding="utf-8"))
    mercedes = next(e for e in data["entries"] if e["id"] == "mercedes")
    secret = mercedes["lines"][0]
    secret["tags"] = ["confidential"]
    (site / "data" / "cv.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

    assert run_render(site).returncode == 0
    assert secret["en"] not in (site / "cv.html").read_text(encoding="utf-8")


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
