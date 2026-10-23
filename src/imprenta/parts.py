"""Parts: how a product's names become the markdown files pandoc concatenates.

Every part is wrapped in a fenced div (`.part .part-<name>`, plus
`.style-<style>` and `.unlisted` from its settings) so a theme can style any
part by name. Two parts are generated rather than read from content:

  toc    a marker that toc.lua replaces with a nav of every heading placed
         after it; settings depth (default 2), pages (default true), title
  terms  a glossary built from the term tables of the product's content files;
         settings title; with more than one labelled source it carries a label
         column so a term used in several places shows its meanings on
         adjacent rows
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from . import content
from .catalog import GENERATED

if TYPE_CHECKING:
    from .catalog import Catalog

BOLD = re.compile(r"\*\*(.+?)\*\*")
TABLE_RULE = re.compile(r"^\|\s*:?-")


# ---------- term tables ----------


def strip_md(s: str) -> str:
    """Plain text of a table cell: no bold/italic markers or escapes."""
    s = s.replace("**", "").replace("\\", "")
    s = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"\1", s)
    return s.strip()


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def column_role(header: str, columns: dict[str, list[str]]) -> str | None:
    """Which glossary role a table header fills, by alias substring; None for none."""
    h = header.lower()
    for role, aliases in columns.items():
        if any(a in h for a in aliases):
            return role
    return None


def parse_tables(text: str, columns: dict[str, list[str]]):
    """Yield (term, literal, meaning, example) from every markdown table whose
    first column is the term (it always is) and whose other columns match the
    glossary roles. Comments and front matter must already be stripped."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("|") and i + 1 < len(lines) and TABLE_RULE.match(lines[i + 1]):
            roles = [column_role(h, columns) for h in split_row(line)]
            if roles:
                roles[0] = "term"
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                cells = split_row(lines[i])
                row = {"term": "", "literal": "", "meaning": "", "example": ""}
                for role, cell in zip(roles, cells):
                    if role in row and not row[role]:
                        row[role] = strip_md(cell)
                if row["term"]:
                    yield row["term"], row["literal"], row["meaning"], row["example"]
                i += 1
            continue
        i += 1


def md_cell(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def terms_rows(cat: Catalog, names: list[str]) -> list[tuple[str, str, str, str, str]]:
    """[(term, literal, meaning, example, label)] from the named content files, in
    order. Rows without a meaning are left out: a glossary needs one."""
    rows = []
    for name in names:
        path = cat.project.content_path(name)
        if not path.exists():
            continue
        label = content.read_meta(path).get("label") or content.default_label(name)
        text = content.strip_comments(content.read_text(path))
        for term, literal, meaning, example in parse_tables(text, cat.term_columns):
            if meaning:
                rows.append((term, literal, meaning, example, str(label)))
    return rows


def terms_markdown(cat: Catalog, names: list[str], settings: dict | None = None) -> str:
    """The glossary part as markdown: one table, alphabetical."""
    settings = settings or {}
    labels = cat.strings
    rows = terms_rows(cat, names)
    order = {label: i for i, label in enumerate(dict.fromkeys(r[4] for r in rows))}
    rows.sort(key=lambda r: (r[0].casefold(), order.get(r[4], 0)))
    title = settings.get("title") or labels.get("terms_title", "Glossary")
    if len(order) > 1:
        head = ["Term", labels.get("terms_label", "Source"), "Meaning", "Example"]
        widths = [16, 14, 38, 32]
        cells = [(r[0], r[4], r[2], r[3]) for r in rows]
    else:
        has_literal = any(r[1] for r in rows)
        head = ["Term", "Literal", "Meaning", "Example"] if has_literal else ["Term", "Meaning", "Example"]
        widths = [18, 16, 38, 34] if has_literal else [18, 46, 36]
        cells = [(r[0], r[1], r[2], r[3]) if has_literal else (r[0], r[2], r[3]) for r in rows]
    lines = [
        f"# {title}",
        "",
        "| " + " | ".join(head) + " |",
        "|" + "|".join(":" + "-" * (w - 1) for w in widths) + "|",
    ]
    lines += ["| " + " | ".join(md_cell(c) for c in row) + " |" for row in cells]
    return "\n".join(lines) + "\n"


# ---------- the table of contents ----------


def toc_markdown(cat: Catalog, settings: dict | None = None) -> str:
    """The marker toc.lua replaces with a nav of everything after it."""
    settings = settings or {}
    title = settings.get("title", cat.strings.get("toc_title", "Contents"))
    attrs = {
        "depth": str(settings.get("depth", 2)),
        "pages": "false" if settings.get("pages") is False else "true",
        "title": str(title).replace('"', "'"),
    }
    attr = " ".join(f'{k}="{v}"' for k, v in attrs.items())
    return f"::: {{.toc-marker {attr}}}\n:::\n"


# ---------- wrapping and assembly ----------


def part_classes(name: str, settings: dict) -> str:
    classes = [".part", f".part-{content.css_name(name)}"]
    if settings.get("style"):
        classes.append(f".style-{settings['style']}")
    if settings.get("toc") is False:
        classes.append(".unlisted")
    return " ".join(classes)


def wrap(markdown: str, name: str, settings: dict) -> str:
    """A part's markdown inside its wrapper div (six colons so the content may
    use ::: fenced divs of its own)."""
    return f":::::: {{{part_classes(name, settings)}}}\n{markdown.rstrip()}\n\n::::::\n"


def assemble(cat: Catalog, product: str, tmp: Path) -> tuple[list[Path], list[str]]:
    """Resolve a product's parts into (markdown files in order, content names).
    Each part is written to `tmp` wrapped in its div; toc and terms are generated."""
    tmp.mkdir(parents=True, exist_ok=True)
    parts = cat.resolve_parts(product)
    names = [n for n, _ in parts if n not in GENERATED]
    files = []
    for i, (name, settings) in enumerate(parts):
        if name == "toc":
            text = toc_markdown(cat, settings)
        elif name == "terms":
            text = terms_markdown(cat, names, settings)
        else:
            text = content.read_text(cat.project.content_path(name))
        out = tmp / f"{product}.{cat.name}.{i:02d}.{content.css_name(name)}.md"
        out.write_text(wrap(text, name, settings), encoding="utf-8")
        files.append(out)
    return files, names


def page_title(cat: Catalog, product: str) -> str:
    """The HTML <title>: the first H1 among the product's content, else its name."""
    for name in cat.content_names(product):
        title = content.first_heading(content.read_text(cat.project.content_path(name)))
        if title:
            return title
    return product


def page_lang(cat: Catalog, product: str) -> str | None:
    """A `lang` declared in any part's front matter (the first wins), else None."""
    for name in cat.content_names(product):
        lang = content.read_meta(cat.project.content_path(name)).get("lang")
        if lang:
            return str(lang)
    return None
