# {{name}}: conventions for Claude Code

This repo is a content project driven by the imprenta engine (pinned in
`pyproject.toml`). There is no build code here: `imprenta` does the arranging
and rendering; this repo holds content, a theme and a catalog.

## Hard rules

- `content/<name>.md` is the only kind of source file. The name is the path
  under `content/` without `.md`. A file starts with optional YAML front matter
  (`label`, the short name the glossary prints; `lang` if the HTML should
  declare one), then its own H1 title, then sections at H2, never deeper than
  H4. A part the catalog gives a `style` (a cover) may open with a paragraph.
  Author notes go at the end inside one `<!-- NOTES … -->` comment and are never
  rendered. Nothing inside it may contain `--`.
- The engine never injects or shifts headings: what is in the file is what
  renders, in every product it is placed in.
- `catalog.main.yaml` has only `defaults`, `rendering`, `strings`, `terms`,
  `groups`, `recipes`, `products`. Everything in a parts list is a name:
  `toc`, `terms`, a group, or a content file. No sigils, no catch-all.
- A product has `parts` (or a `recipe`), a `theme`, `status`, `version`
  (quoted), `variants`, `tags`. Tags are plain words; what they mean is this
  repo's business (its CI), never the engine's.
- Edit catalogs by hand or through `imprenta manager`; never regenerate them
  with a YAML library that drops comments.
- `make check` must pass before a change is done.

## Commands

`make` (check + build everything), `make <product>`, `make <catalog>/<product>`,
`make <product>.<variant>`, `make preview-<catalog>/<product>`, `make manager`,
`make check`, `make status`, `make doctor`, `make setup`, `make clean`. Add
`FORCE=1` to rebuild regardless. Outputs are `output/<product>.<catalog>.<variant>.<ext>`.

## Upgrading the engine

Bump `imprenta[tui]==X.Y.Z` in `pyproject.toml` with that release's notes open,
run `uv lock`, then `make`. The engine's CHANGELOG lists catalog changes a
release needs. A template release of the same number, if there is one, lists
the Makefile, CI and theme changes that go with it (README, "Versions").

## Template versioning

Template `vX.Y.Z` means "set up for imprenta X.Y.Z": the pin is the one
version, and the project version and the release tag must equal it (CI checks,
only in the template repo itself). Patch releases of the engine get no template
release. A release is a `CHANGELOG.md` entry, a merge to `main`, and a tag on
the merge commit. Never tag unless asked.
