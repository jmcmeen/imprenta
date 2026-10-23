"""Content files: `content/<name>.md`, a name being the path under content/ without .md.

A content file is a complete fragment: optional YAML front matter with facts
about the file itself (`label`, `lang`), then its own H1 title, then sections at
H2. Author notes may ride at the end inside an HTML comment; they are stripped
from every output. The engine never injects or shifts headings.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

FRONT_MATTER = re.compile(r"\A---\n(.*?)\n(?:---|\.\.\.)\n", re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)
HEADING = re.compile(r"^(#{1,6})\s")


def split_front_matter(text: str) -> tuple[dict, str]:
    """(front matter as a dict, the markdown after it, leading blank lines dropped)."""
    m = FRONT_MATTER.match(text)
    if not m:
        return {}, text
    meta = yaml.safe_load(m.group(1))
    return (meta if isinstance(meta, dict) else {}), text[m.end() :].lstrip("\n")


def read_text(path: Path) -> str:
    """A content file's markdown with any front matter removed."""
    return split_front_matter(path.read_text(encoding="utf-8"))[1]


def read_meta(path: Path) -> dict:
    """A content file's front matter ({} when there is none or the file is missing)."""
    if not path.exists():
        return {}
    return split_front_matter(path.read_text(encoding="utf-8"))[0]


def strip_comments(text: str) -> str:
    """Drop HTML comment blocks (the author notes)."""
    return COMMENT.sub("", text)


def word_count(path: Path) -> int:
    """Words in a content file, front matter and comments excluded."""
    if not path.exists():
        return 0
    return len(strip_comments(read_text(path)).split())


def first_heading(text: str) -> str | None:
    """The text of the first H1 in a fragment, or None."""
    for line in strip_comments(text).splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def is_placeholder(path: Path) -> bool:
    """True for a file that is only comments (and front matter): allowed, skipped."""
    return not strip_comments(read_text(path)).strip()


def css_name(name: str) -> str:
    """A content name as a CSS class / file token: `shared/intro.en` -> `shared-intro-en`."""
    return re.sub(r"[^A-Za-z0-9_-]+", "-", name)


def default_label(name: str) -> str:
    """A label for a file without one in its front matter: the name's stem, title-cased."""
    return Path(name).name.split(".")[0].replace("-", " ").title()
