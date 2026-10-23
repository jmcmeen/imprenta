# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

