# {{name}}

A content repo arranged and rendered by [imprenta](https://github.com/jmcmeen/imprenta)
{{version}}. It started from `imprenta new`, with some lorem ipsum, a theme and
a catalog: replace the content and the catalog with your own.

## Setup

```sh
brew install uv pandoc node          # or your platform's equivalents
brew install --cask google-chrome    # pagedjs-cli drives it to make PDFs
make setup                           # uv sync, npm ci, fetch the theme fonts, check the tools
make                                 # check, then build every product
```

## What is here

```text
catalog.main.yaml      the catalog: rendering variants, labels, groups, recipes, products
content/               the content: <name>.md files; the name is the path without .md
  lorem.md, ipsum.md       two chapters with term tables (front matter `label`, own H1, H2 sections)
  lorem-cover.md, …        covers: an eyebrow paragraph, the H1 title, an optional subtitle
  shared/welcome.md, …     reusable parts, written once and placed by name
templates/             the theme: leaflet.html and volume.html (pandoc templates), print.css,
                       epub.css, sizes/, palettes/, fonts/ (fetched by make setup)
scripts/fetch_fonts.py downloads the theme fonts (run by make setup)
output/, tmp/          generated, git-ignored; output is flat: <product>.main.<variant>.<ext>
```

Three products are defined: `lorem` and `ipsum` (each a leaflet from the
`leaflet` recipe: cover, welcome, the chapter, a glossary) and `omnibus` (a
volume: cover, table of contents, foreword, both chapters, the combined
glossary, a colophon). `make lorem`, `make omnibus`, `make main/lorem.ebook`.

## Make it yours

1. Replace the files in `content/`. Keep the shape: optional front matter,
   one `# Title`, sections at `##`.
2. Edit `catalog.main.yaml`: your groups, your recipes, your products. Add
   `catalog.<other>.yaml` files for other sets of products (another language,
   a different line) that share the same content.
3. Restyle `templates/`: `print.css` and `epub.css` hold the colors and type,
   `palettes/` and `sizes/` the layers variants pick from, the two `.html`
   files the page frame. Themes are picked per product.
4. `make check` must pass. `make manager` opens a dashboard over it all.

Publishing is yours to add: give products tags (`tags: [release]`) and let your
own CI select them with `imprenta build --tag release`, then upload wherever
you ship.

## Upgrading the engine

Bump `imprenta[tui]==X.Y.Z` in `pyproject.toml` with that release's notes open
and run `uv lock`. The engine's CHANGELOG lists what a release changes in the
catalog and, when the starter files changed with it (Makefile, CI, theme),
says so: run `imprenta new` into a scratch folder with the new engine and diff
it against this repo to see the exact lines.

## Rules the checker enforces

- `content/` holds only `.md` files. Every file starts with its own H1 after
  optional front matter (a styled part such as a cover may open with a
  paragraph), has one H1, sections at H2, nothing deeper than H4.
- Every name in a parts list is `toc`, `terms`, a group or a content file.
- Every product has a status (`draft | ready | published`), a quoted version
  once it leaves draft, known variants and string tags.
- Every rendering variant points at css layers that exist.
