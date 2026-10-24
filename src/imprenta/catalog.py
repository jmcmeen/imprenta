"""A catalog: one set of products arranged from the project's content.

`catalog.<name>.yaml` has only these sections:

    defaults    publishing fields every product inherits (variants, tags)
    rendering   default, variants {name: {renderer, size, palette}}, bundles {name: [variants]}
    strings     reader-facing labels for the generated parts (toc_title, terms_title, terms_label)
    terms       glossary column aliases: columns {term|literal|meaning|example: [headers]}
    groups      named, ordered lists of content names
    recipes     shapes products share: {theme, parts}; `$name` is the product's own name
    products    what gets built: {recipe | theme + parts, status, version, variants, tags}

A part name resolves as a generated part (`toc`, `terms`), then a group
(expanded in place), then a content file. An entry may carry settings as a
one-key mapping: `- toc: {depth: 2}` or `- cover.en: {style: cover, toc: false}`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .project import Project

GENERATED = ("toc", "terms")
PLAN_KEYS = ("status", "version", "variants", "tags")
PRODUCT_KEYS = ("recipe", "theme", "parts", *PLAN_KEYS)
SECTIONS = ("defaults", "rendering", "strings", "terms", "groups", "recipes", "products")
STATUSES = ("draft", "ready", "published")
RENDERERS = ("pdf", "epub")
DEFAULT_THEME = "default"

# How the glossary recognizes a term table's columns when a catalog has no
# `terms.columns`: a header matches a role when it contains one of these.
DEFAULT_TERM_COLUMNS = {
    "term": ["term"],
    "literal": ["literal", "origin", "source", "equivalent"],
    "meaning": ["meaning"],
    "example": ["example", "note"],
}


def substitute(value: Any, product: str) -> Any:
    """Replace `$name` with the product's name throughout a part name or settings mapping."""
    if isinstance(value, str):
        return value.replace("$name", product)
    if isinstance(value, dict):
        return {substitute(k, product): substitute(v, product) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute(v, product) for v in value]
    return value


def normalize_parts(parts: list | None) -> list[tuple[str, dict]]:
    """A parts list as [(name, settings)]."""
    out = []
    for entry in parts or []:
        if isinstance(entry, dict) and len(entry) == 1:
            ((name, settings),) = entry.items()
            out.append((str(name), dict(settings or {})))
        else:
            out.append((str(entry), {}))
    return out


class Catalog:
    """One parsed catalog. Pure over its data plus the project's content folder."""

    def __init__(self, project: Project, name: str, data: dict):
        self.project = project
        self.name = name
        self.data = data or {}

    def __repr__(self) -> str:
        return f"Catalog({self.name!r}, {len(self.products)} products)"

    # ----- sections -----

    @property
    def defaults(self) -> dict:
        """The `defaults` section: publishing fields every product inherits."""
        return self.data.get("defaults") or {}

    @property
    def products(self) -> dict:
        """The `products` section: name to definition, as written."""
        return self.data.get("products") or {}

    @property
    def groups(self) -> dict:
        """The `groups` section: name to ordered list of content names."""
        return self.data.get("groups") or {}

    @property
    def recipes(self) -> dict:
        """The `recipes` section: name to the shape (`theme`, `parts`) products share."""
        return self.data.get("recipes") or {}

    @property
    def strings(self) -> dict:
        """The `strings` section: reader-facing labels for the generated parts and templates."""
        return dict(self.data.get("strings") or {})

    @property
    def term_columns(self) -> dict[str, list[str]]:
        """Role -> header aliases for the glossary, the catalog's over the defaults."""
        cols = dict(DEFAULT_TERM_COLUMNS)
        for role, aliases in ((self.data.get("terms") or {}).get("columns") or {}).items():
            cols[role] = [str(a).lower() for a in (aliases or [])]
        return cols

    # ----- rendering -----

    @property
    def rendering(self) -> dict:
        """The `rendering` section with `variants` and `bundles` always present.

        `products` is accepted as the old name of `bundles`.
        """
        cfg = dict(self.data.get("rendering") or {})
        cfg.setdefault("variants", {})
        cfg.setdefault("bundles", cfg.pop("products", {}))  # `products` is the old name
        return cfg

    @property
    def variants(self) -> dict:
        """Render variants by name: `{renderer, size, palette}`."""
        return self.rendering["variants"]

    @property
    def bundles(self) -> dict:
        """Named groups of variants a sales channel ships together."""
        return self.rendering["bundles"]

    @property
    def default_variant(self) -> str | None:
        """The variant a bare target name means, if the catalog sets one."""
        return self.rendering.get("default")

    def resolve_variant(self, name: str | None = None) -> str:
        """`name`, else the catalog's default; raises KeyError for an unknown one."""
        name = name or self.default_variant
        if name not in self.variants:
            known = ", ".join(sorted(self.variants)) or "none defined"
            raise KeyError(f"Unknown variant '{name}' in catalog.{self.name}.yaml (have: {known})")
        return name

    def variant_renderer(self, variant: str) -> str:
        """`pdf` or `epub` for a variant (pdf when unstated)."""
        return self.variants[variant].get("renderer", "pdf")

    def variant_layers(self, variant: str) -> list[Path]:
        """The css layers a variant adds: size + palette for pdf, optional palette for epub."""
        v = self.variants[variant]
        layers = []
        if v.get("size"):
            layers.append(self.project.templates / "sizes" / f"{v['size']}.css")
        if v.get("palette"):
            layers.append(self.project.templates / "palettes" / f"{v['palette']}.css")
        return layers

    def variant_meta(self, variant: str) -> dict:
        """Pandoc metadata the HTML templates use to link the variant's css layers."""
        v = self.variants[variant]
        m = {"variant": variant, "size": v.get("size"), "palette": v.get("palette")}
        if v.get("size"):
            m["size_css"] = f"sizes/{v['size']}.css"
        if v.get("palette"):
            m["palette_css"] = f"palettes/{v['palette']}.css"
        return m

    def variant_filter(self, variant: str | None = None, bundle: str | None = None) -> list[str] | None:
        """Variant names selected by a --variant / --bundle option, or None for all."""
        if variant:
            return [self.resolve_variant(variant)]
        if bundle:
            if bundle not in self.bundles:
                known = ", ".join(sorted(self.bundles)) or "none defined"
                raise KeyError(f"Unknown bundle '{bundle}' (have: {known})")
            return list(self.bundles[bundle])
        return None

    # ----- products -----

    def product_def(self, product: str) -> dict | None:
        """A product's full definition: its recipe's fields (with `$name` filled in)
        under its own. None if the product does not exist."""
        spec = self.products.get(product)
        if spec is None:
            return None
        spec = dict(spec or {})
        base: dict = {}
        if spec.get("recipe"):
            base = substitute(dict(self.recipes.get(spec["recipe"]) or {}), product)
        merged = {**base, **{k: v for k, v in spec.items() if k != "recipe"}}
        merged.setdefault("theme", DEFAULT_THEME)
        return merged

    def plan(self, product: str) -> dict:
        """A product's publishing plan: defaults with the product's fields on top.
        `variants` falls back to every rendering variant; `tags` to []."""
        plan: dict = {"status": None, "version": None, "variants": None, "tags": None}
        plan.update({k: v for k, v in self.defaults.items() if k in PLAN_KEYS})
        plan.update({k: v for k, v in (self.product_def(product) or {}).items() if k in PLAN_KEYS})
        if plan["variants"] is None:
            plan["variants"] = list(self.variants)
        plan["tags"] = [str(t) for t in (plan["tags"] or [])]
        return plan

    def theme(self, product: str) -> str:
        """The product's theme name, from its definition or recipe, else the default."""
        return (self.product_def(product) or {}).get("theme") or DEFAULT_THEME

    def part_entries(self, product: str) -> list[tuple[str, dict]]:
        """The product's parts list as `(name, settings)` pairs, before groups are expanded."""
        return normalize_parts((self.product_def(product) or {}).get("parts"))

    def resolve_parts(self, product: str) -> list[tuple[str, dict]]:
        """Expand a product's parts: groups in place, generated parts kept, content
        names dropped when their file is missing or is an empty placeholder (only
        comments), since an empty part would still start a page of its own."""
        from . import content

        out = []
        for name, settings in self.part_entries(product):
            names = list(self.groups[name] or []) if name in self.groups else [name]
            for n in names:
                if n in GENERATED:
                    out.append((n, settings if n == name else {}))
                    continue
                path = self.project.content_path(n)
                if path.exists() and not content.is_placeholder(path):
                    out.append((n, settings if n == name else {}))
        return out

    def content_names(self, product: str) -> list[str]:
        """The content files a product renders, in order (generated parts left out)."""
        return [n for n, _ in self.resolve_parts(product) if n not in GENERATED]

    def render_row(self, product: str, variant: str | None = None) -> dict:
        """Everything in the catalog that changes one rendered file (not whether it
        exists): the resolved parts with settings, the theme, strings, glossary
        columns, the product's status/version, and the variant's definition.
        Content (and its front matter) is tracked by file mtime instead."""
        spec = self.product_def(product) or {}
        row = {
            "parts": self.resolve_parts(product),
            "theme": spec.get("theme"),
            "strings": self.strings,
            "terms": self.term_columns,
            "product": {k: v for k, v in spec.items() if k in ("status", "version")},
        }
        if variant is not None:
            row["variant"] = self.variants.get(variant)
        return row

    def output_path(self, product: str, variant: str) -> Path:
        """Flat output: output/<product>.<catalog>.<variant>.<pdf|epub>."""
        return self.project.output / f"{product}.{self.name}.{variant}.{self.variant_renderer(variant)}"
