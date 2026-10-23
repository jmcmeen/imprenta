"""Edit a catalog in place without losing its comments or layout.

The engine reads catalogs with PyYAML, which is fine for reading but drops
every comment on a round trip. Anything that writes a catalog goes through
ruamel.yaml's round-trip loader instead, so comments, quoting and key order
survive each save. Beware: ruamel attaches a comment to the key before it, so
popping a key can take the next comment with it.

    doc = load(project, "en")
    set_field(doc, "handbook", "status", next_status("draft"))
    set_field(doc, "handbook", "version", bump_version("0.1"))
    toggle_tag(doc, "handbook", "release")
    save(project, "en", doc)
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedSeq
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

from .catalog import STATUSES

if TYPE_CHECKING:
    from .project import Project


def yaml_rt() -> YAML:
    y = YAML()  # round-trip mode: keeps comments and key order
    y.preserve_quotes = True
    y.width = 4096  # never re-wrap long lines
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def loads(text: str):
    return yaml_rt().load(text)


def dumps(doc) -> str:
    buf = io.StringIO()
    yaml_rt().dump(doc, buf)
    return buf.getvalue()


def load(project: Project, name: str):
    return loads(project.catalog_path(name).read_text(encoding="utf-8"))


def save(project: Project, name: str, doc) -> Path:
    path = project.catalog_path(name)
    path.write_text(dumps(doc), encoding="utf-8")
    return path


def product_block(doc, product: str):
    """One product's mapping; KeyError if absent."""
    return doc["products"][product]


def set_field(doc, product: str, key: str, value) -> None:
    """Set one publishing field on a product. `version` is always written
    double-quoted (the check requires a string); None removes the field so the
    product falls back to `defaults`."""
    block = product_block(doc, product)
    if value is None:
        block.pop(key, None)
        return
    if key == "version":
        value = DoubleQuotedScalarString(str(value))
    block[key] = value


def get_field(doc, product: str, key: str, default=None):
    """A product's field, falling back to `defaults` for variants and tags."""
    block = product_block(doc, product)
    value = block.get(key, default)
    if value is default and key in ("variants", "tags"):
        value = (doc.get("defaults") or {}).get(key, default)
    return value


def flow(items) -> CommentedSeq:
    seq = CommentedSeq(list(items))
    seq.fa.set_flow_style()
    return seq


def next_status(status) -> str:
    """draft -> ready -> published -> draft."""
    if status not in STATUSES:
        return STATUSES[0]
    return STATUSES[(STATUSES.index(status) + 1) % len(STATUSES)]


def bump_version(version, major: bool = False) -> str:
    """ "0.1" -> "0.2"; major: "0.1" -> "1.0". A missing version starts at "0.1"."""
    if not version:
        return "0.1"
    parts = str(version).split(".")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return str(version)
    if len(nums) == 1:
        nums.append(0)
    if major:
        return f"{nums[0] + 1}.0"
    nums[-1] += 1
    return ".".join(str(n) for n in nums)


def toggle_variant(doc, product: str, variant: str, known) -> list[str]:
    """Add or remove one render variant from a product's subscription. The list
    is written in flow style, ordered as `known`; it is dropped when it comes
    back equal to `defaults.variants`, and the last variant cannot be removed."""
    current = list(get_field(doc, product, "variants") or known)
    if variant in current:
        if len(current) == 1:
            raise ValueError("a product needs at least one variant")
        current.remove(variant)
    else:
        current.append(variant)
    ordered = [v for v in known if v in current]
    defaults = list((doc.get("defaults") or {}).get("variants") or known)
    if ordered == defaults:
        set_field(doc, product, "variants", None)
    else:
        product_block(doc, product)["variants"] = flow(ordered)
    return ordered


def toggle_tag(doc, product: str, tag: str) -> list[str]:
    """Add or remove a tag on a product (flow style; the field is dropped when
    it comes back equal to `defaults.tags`)."""
    current = [str(t) for t in (get_field(doc, product, "tags") or [])]
    if tag in current:
        current.remove(tag)
    else:
        current.append(tag)
    defaults = [str(t) for t in ((doc.get("defaults") or {}).get("tags") or [])]
    if current == defaults:
        set_field(doc, product, "tags", None)
    else:
        product_block(doc, product)["tags"] = flow(current)
    return current
