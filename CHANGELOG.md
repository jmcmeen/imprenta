# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Documentation site** at <https://jmcmeen.github.io/imprenta/>: the README, the
  command line help rendered from the parser, the `Project` / `Catalog` / `Target` API
  from docstrings, and the changelog. Built with MkDocs Material (`make docs`,
  `make docs-serve`, dependency group `docs`) and published by `docs.yml` on pushes to
  main. Documentation-only changes skip CI and so cut no release.
- `imprenta new --pin` accepts only a release number (`X.Y` or `X.Y.Z`), since the
  value lands after `==` in the generated `pyproject.toml`.

### Fixed

- The starter written by `imprenta new` no longer carries the old template repo's
  versioning rules in its `CLAUDE.md` and check workflow.
- `imprenta new` builds the project beside the destination and moves it into place
  when complete, so an interrupted run leaves nothing half-written, not even parent
  folders it created; `imprenta new .` fills an empty current directory; a destination
  that is a file or a symlink, or that something else filled meanwhile, is refused with
  a message instead of a traceback.
- The starter Makefile quotes the goal it hands to `imprenta build`.

## [0.1.1] - 2026-10-24

### Added

- **`imprenta new DIR [--name NAME] [--pin VERSION]`** writes the starter project: a catalog, lorem
  ipsum content with term tables, a theme (`leaflet` and `volume`), `scripts/fetch_fonts.py`,
  the Makefile, the Node pin for pagedjs-cli and a check workflow, with `pyproject.toml`
  pinned to the engine that wrote it. The starter ships inside the package
  (`imprenta/data/starter/`) and the test suite checks it, so it cannot drift from the
  engine. It replaces the separate imprenta-template repo. To see what a release changed
  in the starter, write it into a scratch folder with the new engine and diff.

## [0.1.0] - 2026-10-23

### Added

- **The content arranger.** `content/<name>.md` files are arranged into products by
  `catalog.<name>.yaml` files: `defaults`, `rendering` (render variants), `strings`
  (labels), `terms` (glossary column aliases), `groups`, `recipes` (shapes with
  `$name` substitution) and `products` (an ordered `parts` list, a `theme`, and the
  fields `status`, `version`, `variants`, `tags`). Nothing in the engine knows what the
  content is about or what language it is in.
- **Generated parts.** `toc` (positional: lists every heading placed after it, with
  page numbers resolved by Paged.js; settings `depth`, `pages`, `title`) and `terms`
  (a glossary built from the content's term tables, with a label column when the
  terms come from more than one labelled file).
- **Styled parts.** Any content part may carry `{style: <name>, toc: false}`; the
  build wraps every part in `<div class="part part-<name> style-<style>">` for the
  theme to style. A cover is a content file with `style: cover`. A content file
  that is only comments (a placeholder) is skipped, so it never costs a page.
- **Rendering.** pandoc + pagedjs-cli (Paged.js in headless Chrome) for PDF variants,
  pandoc EPUB 3 for `renderer: epub` variants, with size and palette css layers.
  Incremental builds keyed on file mtimes plus a stamp of the catalog rows and the
  imprenta version.
- **Targets.** `(catalog, product, variant)`; `imprenta build` takes `<catalog>`,
  `<product>`, `<catalog>/<product>`, each optionally `.<variant>`, or nothing for
  everything; `--tag` narrows to products carrying a tag. `imprenta affected --since`
  maps changed paths to targets for incremental CI.
- **Validation.** `imprenta check` enforces the content rules (one leading H1, H2
  sections, max H4, front matter) and the catalog rules (every name resolves, settings
  per part kind, recipes, themes, publishing fields, rendering layers).
- **Catalog editing.** `imprenta.edit` writes catalogs through ruamel.yaml's
  round-trip mode so comments survive.
- **The manager.** `imprenta manager` (extra `imprenta[tui]`): a Textual dashboard of
  every product with a product screen for sync-free publishing fields, variant
  subscriptions, builds and outputs.
- **API.** `imprenta.Project` as the entry point: catalogs, targets, build, check.

