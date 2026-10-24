"""Targets: what gets built, and which of them a change affects.

A target is (catalog, product, variant). The universe is every product of
every catalog times the variants it subscribes; a tag narrows it to the
products carrying that tag. Given the paths that changed since a commit,
`affected_targets` works out which targets need rebuilding:

  content/<name>.md            every target, in any catalog, whose resolved parts include <name>
  catalog.<name>.yaml          that catalog's targets whose rendered rows changed
                               (all of them if the old catalog is unknown)
  templates/sizes|palettes/*   every target whose variant uses that layer
  templates/print.css, *.html  every pdf target;  templates/epub.css  every epub target
  templates/** (anything else) everything

Anything else rebuilds nothing. Because the engine lives in a package, a
version bump invalidates outputs through the build stamp instead of a path.
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import TYPE_CHECKING, NamedTuple

import yaml

if TYPE_CHECKING:
    from .catalog import Catalog
    from .project import Project

CATALOG_FILE = re.compile(r"^catalog\.([A-Za-z0-9_-]+)\.yaml$")
CONTENT_FILE = re.compile(r"^content/(.+)\.md$")
LAYER_FILE = re.compile(r"^templates/(sizes|palettes)/([^/]+)\.css$")
RENDERER_FILES = {
    "pdf": re.compile(r"^templates/(print\.css|[^/]+\.html)$"),
    "epub": re.compile(r"^templates/epub\.css$"),
}


class Target(NamedTuple):
    """One thing to build: a product of a catalog in one render variant."""

    catalog: str
    product: str
    variant: str

    @property
    def key(self) -> str:
        """`catalog/product/variant`, the stable id a manifest or stamp records."""
        return f"{self.catalog}/{self.product}/{self.variant}"

    def __str__(self) -> str:
        return f"{self.catalog}/{self.product} {self.variant}"


def all_targets(cats: dict[str, Catalog], only=None, tag: str | None = None) -> list[Target]:
    """Every buildable target of the given catalogs, narrowed by `only` (a variant
    filter) and `tag` (products carrying it)."""
    out = []
    for name, cat in cats.items():
        for product in cat.products:
            plan = cat.plan(product)
            if tag is not None and tag not in plan["tags"]:
                continue
            out += [
                Target(name, product, v) for v in cat.variants if v in plan["variants"] and (only is None or v in only)
            ]
    return out


def affected_targets(changed, cats: dict[str, Catalog], only=None, tag=None, old_cats=None) -> list[Target]:
    """Targets to rebuild for repo-relative changed paths (see the module docstring).
    `old_cats` maps catalog names to their Catalog as of the last publish; a
    missing entry means unknown, so that catalog rebuilds entirely on a change."""
    everything = all_targets(cats, only, tag)
    old_cats = old_cats or {}
    out: set[Target] = set()
    for path in changed:
        path = path.replace(os.sep, "/")
        m = CATALOG_FILE.match(path)
        if m:
            name = m.group(1)
            mine = [t for t in everything if t.catalog == name]
            old = old_cats.get(name)
            if old is None:
                out.update(mine)
            else:
                out.update(
                    t
                    for t in mine
                    if old.render_row(t.product, t.variant) != cats[name].render_row(t.product, t.variant)
                )
            continue
        layer = LAYER_FILE.match(path)
        if layer:
            axis = {"sizes": "size", "palettes": "palette"}[layer.group(1)]
            out.update(t for t in everything if cats[t.catalog].variants[t.variant].get(axis) == layer.group(2))
            continue
        renderer = next((r for r, rx in RENDERER_FILES.items() if rx.match(path)), None)
        if renderer:
            out.update(t for t in everything if cats[t.catalog].variant_renderer(t.variant) == renderer)
            continue
        if path.startswith("templates/"):
            return everything
        m = CONTENT_FILE.match(path)
        if m:
            name = m.group(1)
            out.update(t for t in everything if name in {n for n, _ in cats[t.catalog].resolve_parts(t.product)})
    return [t for t in everything if t in out]


def changed_since(root, commit: str | None) -> list[str] | None:
    """Paths changed between `commit` and HEAD, or None if `commit` is unknown here."""
    if not commit:
        return None
    try:
        subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=root, check=True, capture_output=True)
        out = subprocess.run(
            ["git", "diff", "--name-only", commit, "HEAD"], cwd=root, check=True, capture_output=True, text=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return [line for line in out.stdout.splitlines() if line]


def catalogs_at(project: Project, commit: str) -> dict[str, Catalog]:
    """{name: Catalog} as committed at `commit`, for the catalogs readable there."""
    from .catalog import Catalog

    out = {}
    for name in project.catalog_names():
        try:
            text = subprocess.run(
                ["git", "show", f"{commit}:catalog.{name}.yaml"],
                cwd=project.root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
        out[name] = Catalog(project, name, yaml.safe_load(text) or {})
    return out


# ---------- named targets (the make / CLI surface) ----------
#
#   <catalog>                      every product of that catalog
#   <product>                      that product in every catalog that has it
#   <catalog>/<product>            one product
#   ...  .<variant>                one variant, subscribed or not


class SpecError(ValueError):
    pass


def parse_spec(project: Project, spec: str) -> tuple[str | None, str | None, str | None]:
    """'[<catalog>/]<product>[.<variant>]' or '<catalog>' -> (catalog, product, variant),
    any of which may be None. Raises SpecError for names that exist nowhere."""
    catname, name = spec.split("/", 1) if "/" in spec else (None, spec)
    product, variant = name.split(".", 1) if "." in name else (name, None)
    names = project.catalog_names()
    if catname is None and product in names and variant is None:
        return product, None, None
    if catname is not None and catname not in names:
        raise SpecError(f"Unknown catalog '{catname}' (have: {', '.join(names) or 'none'})")
    where = [catname] if catname else [n for n in names if product in project.catalog(n).products]
    if not where:
        raise SpecError(f"Unknown product '{product}': not in any catalog (try `imprenta status`)")
    for n in where:
        if product not in project.catalog(n).products:
            raise SpecError(f"Unknown product '{product}' in catalog.{n}.yaml (try `imprenta status`)")
    return catname, product, variant


def spec_targets(project: Project, spec: str) -> list[Target]:
    """The targets one spec stands for: subscribed variants unless one is named."""
    catname, product, variant = parse_spec(project, spec)
    if product is None:
        return all_targets({catname: project.catalog(catname)})
    where = [catname] if catname else [n for n in project.catalog_names() if product in project.catalog(n).products]
    out = []
    for n in where:
        cat = project.catalog(n)
        if variant:
            names = [cat.resolve_variant(variant)]
        else:
            plan = cat.plan(product)
            names = [v for v in cat.variants if v in plan["variants"]]
        out += [Target(n, product, v) for v in names]
    return out
