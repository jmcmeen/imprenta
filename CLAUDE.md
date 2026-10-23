# imprenta: conventions for Claude Code

## What this is

A content arranger and styler. It is a Python package (`src/imprenta`) with a CLI (`imprenta`), an
optional Textual TUI (`imprenta[tui]`) and a public API (`imprenta.Project`).
The README describes the model; this file is about working on the code.

## Hard rules

- **Nothing content-specific.** No countries, languages, brands, slang, guides
  or books in code, comments, docstrings, tests or docs. Examples use neutral
  names (`intro`, `alpha`, `almanac`, `leaflet`, `release`). What a tag means,
  where outputs are published, what a glossary column is called: all of that is
  the content repo's business and lives in its catalog or its own scripts.
- **The engine never injects or shifts headings.** What is in a content file
  is what renders. Themes style; they do not restructure.
- **A catalog has exactly these sections:** `defaults`, `rendering`,
  `strings`, `terms`, `groups`, `recipes`, `products`. Adding a field is an
  API change: update `catalog.py`, `check.py`, the README and the CHANGELOG
  together.
- **Everything in a parts list is a name.** No sigils, no catch-all. Names
  resolve as generated part, group, content file, in that order.
- **Catalogs are written only through `imprenta.edit`** (ruamel round-trip).
  PyYAML's dump drops comments. ruamel attaches a comment to the key before
  it, so popping a key can take the next comment with it.
- **Paged.js matches break rules by selector**, not computed style. To keep an
  element from breaking, exclude it from the rule; a later `break-before:
  auto` does not undo an earlier `page`.

## Layout

```text
src/imprenta/
  project.py   Project: root, dirs, catalogs (cached on mtime), content names, targets, build, check
  catalog.py   Catalog: sections, rendering, product_def (recipes + $name), plan, resolve_parts, render_row
  content.py   front matter, comments, headings, word counts, css-safe names
  parts.py     generated parts (toc marker, terms glossary), part wrapping, assemble
  render.py    pandoc / pagedjs-cli / Chrome, doctor, asset copying, the packaged toc.lua
  build.py     freshness (inputs + stamp), building one target
  targets.py   Target, all_targets, affected_targets, changed_since, spec parsing
  check.py     the validator (content rules + catalog rules)
  edit.py      round-trip catalog editing
  cli.py       argparse entry point; tui.py  the manager (textual, optional)
  data/toc.lua the pandoc filter behind the positional table of contents
tests/         pytest; conftest builds a two-catalog sample project in tmp_path
```

## Working here

- `make install` (uv sync with the dev and TUI extras), `make test`, `make
  lint`, `make fmt`, `make check` (what CI runs). Python ≥ 3.10.
- Versions come from `vX.Y.Z` tags via hatch-vcs. `release.yml` bumps the patch
  on every green merge to main and rolls `CHANGELOG.md`'s Unreleased section
  into the release; a minor or major bump is a manual run of that workflow.
  Add every user-visible change under `## [Unreleased]` in the same commit.
- `publish.yml` publishes to PyPI on a release (trusted publishing, environment
  `pypi`). Content repos pin `imprenta==X.Y.Z`.
- Tests never call pandoc or Chrome. Rendering is exercised from a content repo
  (`imprenta build`), the logic around it is what the suite covers.
- The TUI builds through `python -m imprenta build …` in a worker thread so
  its output streams into the log pane; it never imports make.
