#!/usr/bin/env bash
# List every placeholder still on the site and fail if there is any.
# Run before publishing:  tools/check_todos.sh
#
# A placeholder is marked twice (see README.md): an HTML comment
# "<!-- TODO(felix): … -->" that says what's missing, and the class "todo" on
# the element that shows it. This script lists the comments, and also counts
# elements with the class "todo", so a marker that lost its comment still fails.
set -euo pipefail
cd "$(dirname "$0")/.."

# All pages, including untracked ones (a new page is exactly where a stray
# placeholder hides). --exclude-dir keeps other worktrees out.
search() { grep -r -n -o --include='*.html' --exclude-dir=.worktrees --exclude-dir=.git "$@" . | sed 's|^\./||'; }

# One line per TODO(felix) comment: "page:line:text", sorted by page.
items=$(search 'TODO(felix):[^>]*' | sed -E 's/ *--$//; s/TODO\(felix\): *//' | sort -t: -k1,1 -k2,2n || true)
# Elements carrying the class "todo" (class attribute containing the word).
marked=$(search -E 'class="([^"]* )?todo( [^"]*)?"' | wc -l)

count=$(printf '%s' "$items" | grep -c . || true)
if [ "$count" -eq 0 ] && [ "$marked" -eq 0 ]; then
  echo "No TODO(felix) placeholders left."
  exit 0
fi

echo "$count TODO(felix) item(s), $marked element(s) with class \"todo\":"
printf '%s\n' "$items" | awk -F: '$1 != page { page = $1; print "\n" page } { sub(/^[^:]*:/, ""); print "  " $0 }'
exit 1
