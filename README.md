# imprenta

A content arranger and styler. Markdown files go in, products (PDF and EPUB)
come out, and a catalog says how the one becomes the other. imprenta knows
content, parts, groups, recipes, products, themes and render variants. It
knows nothing about what the content is about or what language it is in.

```sh
pip install imprenta            # the engine and its CLI
pip install 'imprenta[tui]'     # plus the manager, a terminal dashboard
```

Rendering is done by tools a content repo installs itself: [pandoc](https://pandoc.org),
[pagedjs-cli](https://pagedjs.org) (Paged.js in headless Chrome) and a Chrome
or Chromium. `imprenta doctor` says which are missing. The quickest start is
the [imprenta-template](https://github.com/jmcmeen/imprenta-template) repo,
which has all of this wired up around some lorem ipsum.

## The model

A **project** is a folder with `content/`, `templates/` and one or more
`catalog.<name>.yaml` files. Outputs land flat in `output/` as
`<product>.<catalog>.<variant>.<pdf|epub>`.

**Content** is `content/<name>.md`; the name is the path under `content/`
without `.md`, so `intro`, `intro.es` and `shared/colophon` are all just names.
A file is a complete fragment: optional YAML front matter with facts about the
file itself (`label`, the short name a glossary prints; `lang`, if the HTML
should declare one), then its own `# Title`, then sections at `##`, never
deeper than `####`. Author notes may ride at the end inside one HTML comment;
every output strips them. imprenta never injects or shifts a heading.

A **catalog** is one set of products. Several may share `content/`:

```yaml
defaults:
  variants: [letter]
  tags: []

rendering:
  default: letter
  variants:
    letter: {renderer: pdf, size: letter, palette: color}   # print.css + sizes/letter.css + palettes/color.css
    mono:   {renderer: pdf, size: letter, palette: mono}
    ebook:  {renderer: epub}                                # pandoc EPUB 3 + epub.css
  bundles:
    shop: [letter, mono]

strings: {toc_title: Contents, terms_title: Glossary, terms_label: Source}

groups:                      # named, ordered selections of content
  spring: [march, april, may]

recipes:                     # a shape many products share; $name is the product's own name
  leaflet:
    theme: leaflet
    parts:
      - $name-cover: {style: cover, toc: false}
      - intro
      - $name
      - terms

products:
  march: {recipe: leaflet, status: draft, version: "0.1", tags: [release]}
  april: {recipe: leaflet, status: draft, version: "0.1"}
  almanac:
    theme: volume
    version: "0.1"
    parts:
      - almanac-cover: {style: cover, toc: false}
      - toc: {depth: 2}
      - foreword
      - spring
      - terms
```

**Everything in a parts list is a name**, resolved in order: a generated part
(`toc`, `terms`), a group (expanded in place), a content file. There are no
sigils and no catch-all; a product lists exactly what it contains, and
`imprenta check` fails on a name that resolves to nothing. An entry may carry
settings as a one-key mapping.

- `toc` is positional: it lists the headings of everything placed after it, to
  `depth`, with page numbers resolved by Paged.js (`pages: false` turns them
  off, `title` overrides the label).
- `terms` is a glossary built from the term tables in the product's content.
  `terms.columns` in the catalog maps the roles term, literal, meaning and
  example to header words. With terms from more than one labelled file the
  table carries a label column, so a term used in several places shows its
  meanings on adjacent rows.
- Any content part may take `style: <name>` (the theme styles `.style-<name>`)
  and `toc: false` (its headings stay out of every table of contents). Every
  part is wrapped in `<div class="part part-<name>">`, so a theme can style any
  part by name. A cover is a content file with `style: cover`.

A **product** has a `parts` list, a `theme` (`templates/<theme>.html`) and its
own `status` (`draft | ready | published`), `version` (the edition, a quoted
string, required once status leaves draft), `variants` (which renderings to
build) and `tags` (plain strings; imprenta only ever uses them to select:
`imprenta build --tag release`). What a tag means is the content repo's
business, for example its own CI uploading tagged products somewhere.

## Commands

```sh
imprenta build                      # everything every catalog subscribes (incremental)
imprenta build main                 # one catalog
imprenta build april                # one product, in every catalog that has it
imprenta build main/april.ebook     # one catalog's product, one variant (subscribed or not)
imprenta build --tag release        # only tagged products
imprenta build --preview main/april # HTML with the Paged.js polyfill, for a live browser preview
imprenta check                      # content and catalog rules; exit 1 on an error
imprenta status                     # every product of every catalog
imprenta affected --since <commit>  # the targets a change set rebuilds (for incremental CI)
imprenta doctor                     # pandoc, node, pagedjs-cli, Chrome, theme fonts
imprenta manager                    # the TUI
```

Builds are incremental: an output newer than its inputs and built from the
same catalog rows and the same imprenta version is skipped. Editing one
product's line never makes the others stale.

## The API

The CLI and the TUI are thin layers over one object:

```python
from imprenta import Project

project = Project.find()                       # walk up from the cwd to the catalogs
for target in project.targets(tag="release"):  # Target(catalog, product, variant)
    project.build(target)                      # -> output path
errors, warnings = project.check()
cat = project.catalog("main")
cat.plan("april")                              # {status, version, variants, tags}
cat.resolve_parts("almanac")                   # [(name, settings), …]
project.targets_since("abc123")                # what a commit range affects
```

`imprenta.edit` writes a catalog back through ruamel.yaml's round-trip mode, so
comments and formatting survive (`set_field`, `toggle_variant`, `toggle_tag`,
`next_status`, `bump_version`).

## The manager

`imprenta manager` is a Textual dashboard: one row per product of every catalog
with status, edition, tags, part count, word count and last build. Enter opens
the product with its parts, settings, every variant's output, and the controls:
`t` status, `v`/`V` edition, `a` tag, `1`–`9` variant subscriptions, `b` build,
`o` open, `c` check, `y` edit the catalog, `g` commit and push.

## Themes

A theme is `templates/<theme>.html` (a pandoc template wrapping `$body$`) plus
`templates/print.css`, `templates/epub.css`, `templates/sizes/<size>.css`,
`templates/palettes/<palette>.css` and `templates/fonts/`. A product picks its
theme by name; a variant picks the size and palette layers. The template repo
ships a complete theme to start from.
