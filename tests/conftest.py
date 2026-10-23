"""A small project on disk: two catalogs sharing one content folder."""

from pathlib import Path

import pytest

from imprenta import Project

VARIANTS = """\
rendering:
  default: letter
  variants:
    letter: {renderer: pdf, size: letter, palette: color}
    mono:   {renderer: pdf, size: letter, palette: mono}
    ebook:  {renderer: epub}
  bundles:
    shop: [letter, mono]
"""

MAIN = (
    """\
defaults:
  variants: [letter]

"""
    + VARIANTS
    + """\
strings: {toc_title: Contents, terms_title: Glossary, terms_label: Source}

groups:
  all: [alpha, beta]
  first: [alpha]

recipes:
  leaflet:
    theme: leaflet
    parts:
      - $name-cover: {style: cover, toc: false}
      - intro
      - $name
      - terms
      - back

products:
  alpha: {recipe: leaflet, status: draft, version: "0.1", tags: [release]}
  beta:  {recipe: leaflet, status: draft, version: "0.1"}
  anthology:
    theme: volume
    version: "0.1"
    parts:
      - anthology-cover: {style: cover, toc: false}
      - toc: {depth: 2}
      - foreword
      - all
      - terms
      - afterword
"""
)

OTHER = (
    """\
defaults:
  variants: [letter, ebook]

"""
    + VARIANTS
    + """\
strings: {toc_title: Índice, terms_title: Glosario, terms_label: Fuente}
terms:
  columns:
    term: [término]
    meaning: [significado]
    example: [ejemplo]

groups:
  all: [alpha.es]

products:
  alpha: {theme: leaflet, status: ready, version: "1.0", parts: [intro.es, alpha.es, terms]}
"""
)

CHAPTER = """\
---
label: {label}
---

# {title}

Intro paragraph.

## Everyday words

| Term | Literal | Meaning | Example |
| --- | --- | --- | --- |
| **Tío** | Uncle | Dude | *Oye, tío* |
| **Guay** | N/A | Cool | |

Prose with **molar** (no definition).

<!-- NOTES
| **Secret** | x | y | z |
-->
"""


def write_project(root: Path) -> Project:
    content = root / "content"
    (content / "shared").mkdir(parents=True)
    (content / "alpha.md").write_text(CHAPTER.format(label="Alpha", title="All about alpha"))
    (content / "beta.md").write_text(CHAPTER.format(label="Beta", title="All about beta").replace("Tío", "Pata"))
    (content / "alpha.es.md").write_text(
        "---\nlabel: Alfa\nlang: es\n---\n\n# Todo sobre alfa\n\n"
        "| Término | Significado | Ejemplo |\n| --- | --- | --- |\n| **Tío** | Colega | *Oye, tío* |\n"
    )
    for name in ("alpha-cover", "beta-cover", "anthology-cover"):
        (content / f"{name}.md").write_text(f"The eyebrow\n\n# {name.replace('-', ' ').title()}\n")
    (content / "intro.md").write_text("# Welcome\n\nHello.\n")
    (content / "intro.es.md").write_text("<!-- pendiente -->\n")
    (content / "foreword.md").write_text("# Foreword\n\nHi.\n")
    (content / "afterword.md").write_text("# Afterword\n\nBye.\n")
    (content / "shared" / "colophon.md").write_text("# Colophon\n\nSet in type.\n")
    # no back.md: a recipe may name a part that does not exist yet (it is skipped at build, flagged by check)
    templates = root / "templates"
    for sub in ("sizes", "palettes", "fonts"):
        (templates / sub).mkdir(parents=True)
    (templates / "leaflet.html").write_text('<html><title>$title$</title><main class="leaflet">$body$</main></html>\n')
    (templates / "volume.html").write_text('<html><title>$title$</title><main class="volume">$body$</main></html>\n')
    (templates / "print.css").write_text("body {}\n")
    (templates / "epub.css").write_text("body {}\n")
    (templates / "sizes" / "letter.css").write_text("@page { size: letter; }\n")
    (templates / "palettes" / "color.css").write_text("")
    (templates / "palettes" / "mono.css").write_text("")
    (root / "catalog.main.yaml").write_text(MAIN)
    (root / "catalog.other.yaml").write_text(OTHER)
    return Project(root)


@pytest.fixture
def project(tmp_path) -> Project:
    return write_project(tmp_path)
