# felix-muehlenberend.de

Personal website of Felix Mühlenberend: a short bio, his projects with silent
looping clips (each with its own page), links to his CV as PDF (German and
English) and a legal page. Plain static HTML and CSS with one small script
(`site.js`, pause controls for the clips). No build step on the server: the
project rows are rendered into the HTML from Felix's CV data before
committing (below).
Served by GitHub Pages from the root of `main`.

Pages: `index.html` (Home), `projects/*.html` (one page per project),
`legal.html` (Impressum / Datenschutz), `404.html` (served by GitHub Pages
for any missing path, so it uses root-relative paths). `files/` holds the
PDFs: both CVs (below) and the theses. There is no HTML CV page: Felix
replaced `cv.html` with the two PDF links on 25.11.2026.
`demos/` holds self-contained browser demos (the gato_visualizer replay).
The home page has no nav bar (its header holds the name and the links),
and each subpage has one small link back home.

## Preview

    python3 -m http.server -d . 8000

then open http://localhost:8000/.

## No external resources

Every file the site uses lives in this repo: system fonts, no web fonts, no
CDN, no analytics, no cookies, no embeds. Each external request would send
the visitor's IP address (personal data) to a third party. Under German
privacy law (GDPR, § 25 TDDDG) that needs a legal basis or consent; in 2022
LG München I awarded damages against a site that loaded Google Fonts from
Google's servers. Without third parties the site needs no consent banner. Details: the guides
`docs/guides/personal-website.md` (§3.4–3.5) and
`docs/guides/personal-website-demos.md` in the Bewerbung repo. Links to other
sites are fine; loading things from them is not.

Clips are self-hosted silent videos without `autoplay`: `site.js` starts them
unless the visitor prefers reduced motion, and adds a pause button to each
(WCAG 2.2.2).

## Placeholders

Content that is still missing is marked twice: an HTML comment
`<!-- TODO(felix): … -->` saying what's missing, and the class `todo` on the
element (shown with a red background or dashed outline). Before publishing,
run

    tools/check_todos.sh

It lists every item by page and exits non-zero while any are left. Then

    python3 tools/check_links.py

checks that no page loads anything from another origin and that every
internal link and media path resolves, and lists the files in `media/`
and `files/` that no page uses, with the total size.

## Content from cv.yaml

The project rows on the home page (the main list and "More projects") are
generated from Felix's CV data in the Bewerbung repo (`cv/data/cv.yaml`),
the same file the PDF CVs are built from: one row per entry with a `web:`
block (order, section, title, meta line, summary, clip, links; schema in
that repo's `cv/README.md`).

**Edit project text in Bewerbung's `cv.yaml`, never in the HTML
between the markers** `<!-- BEGIN generated: … -->` / `<!-- END generated:
… -->`: the next render overwrites it. Everything outside the markers
(header with the contact links, bio, timeline) is hand-written. Then:

    python3 tools/render.py

(Python 3 with PyYAML and Jinja2, the CV generator's libraries.) Commit the
re-rendered `index.html`.

### Setup on a new machine

The script reads the data through a symlink in `data/`, relative to
this repo, so both repos must sit where they do here
(`~/_Projects/felixmueh.github.io` and `~/_Documents/Bewerbung`):

    mkdir -p data
    ln -s ../../../_Documents/Bewerbung/cv/data/cv.yaml data/cv.yaml

Without it `tools/render.py` stops with a message; there is no cached
copy to fall back on.

### Privacy: why `data/` is never committed

`cv.yaml` holds Felix's street address, phone number and date of birth,
and GitHub Pages publishes everything committed to this repo. So `data/`
is in `.gitignore`, and the script takes nothing from `person` (name,
e-mail, GitHub and LinkedIn are public; the headers that show them are
hand-written). `tools/tests/test_render.py` renders with the real data and
fails if any private `person` value reaches a page:

    python3 -m pytest tools/tests    # any Python with pytest, PyYAML, Jinja2

Before committing, check that `git ls-files data` prints nothing.

### The CV PDFs

The home page header links two CVs, `CV (DE)` and `CV (EN)`:
`files/Muehlenberend-Felix_Lebenslauf.pdf` (German) and
`files/Muehlenberend-Felix_CV.pdf` (English, built from `cv/jobs/_public`;
how to rebuild and copy it: that job.yaml). 404.html links them too. Both
are built in the Bewerbung repo without address, phone, birth date, photo
or signature, and copied here by hand after a `cv.yaml` change. The same
test file checks both copies with pdftotext against the private `person`
values, and fails while one of them is missing.

## Layout prototype

The home page follows layout variant A, chosen on 24.11.2026 from three
variants. The throwaway prototype with all three (A, B, C) and the reasons
for the choice is on the branch `prototype-layout` (`prototype/README.md`).
