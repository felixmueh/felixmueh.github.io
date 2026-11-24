# felix-muehlenberend.de

Personal website of Felix Mühlenberend: a short bio, his projects with silent
looping clips (each with its own page), an HTML CV and a legal page. Plain
static HTML and CSS with one small script (`site.js`, pause controls for the
clips); no build step. Served by GitHub Pages from the root of `main`.

Pages: `index.html` (Home), `projects/*.html` (one page per project),
`cv.html`, `legal.html` (Impressum / Datenschutz).

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

It lists every item by page and exits non-zero while any are left.

## CV page

`cv.html` is for now a hand-written mock based on the CV data in the
Bewerbung repo (`cv/data/cv.yaml`). It will later be generated from that
data; once that exists, don't edit `cv.html` by hand. It deliberately leaves
out street address, phone, date of birth and photo.

## Layout prototype

The home page follows layout variant A, chosen on 24.11.2026 from three
variants. The throwaway prototype with all three (A, B, C) and the reasons
for the choice is on the branch `prototype-layout` (`prototype/README.md`).
