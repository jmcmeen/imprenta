"""Validate a project: its content files and its catalogs.

Content rules:
  - content/ holds only .md files (in subfolders if you like); every file,
    after optional YAML front matter and ignoring HTML comments, starts with
    its own H1 (a part some catalog gives a `style` may open with a
    paragraph), has exactly one H1, keeps sections at H2 and never goes deeper
    than H4; an empty placeholder (comment only) is allowed; front matter must
    be a mapping; a file no product of any catalog uses is a warning.

Catalog rules (every catalog.<name>.yaml):
  - only the sections defaults / rendering / strings / terms / groups /
    recipes / products; `defaults.variants` lists known variants;
  - rendering names a default variant; a pdf variant has a size and a palette
    whose css layer exists, an epub variant has no size and templates/epub.css
    exists; bundles only list known variants;
  - groups list existing content names and never share a name with a
    generated part, a product or a content file;
  - a recipe has theme + parts; `$name` appears only in recipes;
  - every product has a parts list (its own or its recipe's) whose names are
    `toc`, `terms`, a group or a content file, with settings per part kind
    (toc: depth int, pages bool, title str; terms: title str; a content part:
    style str, toc bool); its theme names an existing templates/<theme>.html;
    status is draft | ready | published; version is a quoted string, required
    once status leaves draft; variants and tags are lists of known / string values.

`run(project)` returns (errors, warnings); errors fail `imprenta check`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

from . import content
from .catalog import DEFAULT_THEME, GENERATED, PRODUCT_KEYS, SECTIONS, STATUSES, substitute
from .targets import CATALOG_FILE

if TYPE_CHECKING:
    from .project import Project

TOC_SETTINGS = {"depth": int, "pages": bool, "title": str}
TERMS_SETTINGS = {"title": str}
PART_SETTINGS = {"style": str, "toc": bool}
OLD_SECTION_HINTS = {
    "lang": " (the engine has no language concept: a name like intro.en is just a name)",
    "sync": " (publishing is not the engine's business: give products a tag instead)",
}


# ---------- content ----------


def check_body(path, *, styled: bool = False) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    raw = path.read_text(encoding="utf-8")
    m = content.FRONT_MATTER.match(raw)
    offset = 0
    text = raw
    if m:
        try:
            meta = yaml.safe_load(m.group(1))
            if not isinstance(meta, dict):
                errors.append(f"{path}: front matter must be a mapping (e.g. label: …)")
        except yaml.YAMLError as e:
            errors.append(f"{path}: front matter is not valid YAML ({e})")
        offset = m.group(0).count("\n")
        text = raw[m.end() :]
    lines = content.strip_comments(text).splitlines()
    in_fence = False
    first_text_seen = False
    h1 = 0
    for n, line in enumerate(lines, 1 + offset):
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line.strip():
            continue
        hm = content.HEADING.match(line)
        if not first_text_seen:
            first_text_seen = True
            if not (hm and len(hm.group(1)) == 1) and not styled:
                errors.append(f"{path}:{n}: content must start with its H1 title")
        if hm:
            level = len(hm.group(1))
            if level == 1:
                h1 += 1
                if h1 > 1:
                    errors.append(f"{path}:{n}: second H1 (a file has one title; sections are H2)")
            if level > 4:
                errors.append(f"{path}:{n}: heading deeper than H4 (H{level})")
    if first_text_seen and h1 == 0:
        errors.append(f"{path}: no H1 title")
    if raw and not raw.endswith("\n"):
        warnings.append(f"{path}: missing trailing newline")
    return errors, warnings


# ---------- catalog pieces ----------


def check_version(where, label, row) -> list[str]:
    errors = []
    version = row.get("version")
    if version is not None and not isinstance(version, str):
        errors.append(f"{where}: {label}.version must be a quoted string (got {version!r})")
    elif row.get("status") in ("ready", "published") and not version:
        errors.append(f"{where}: {label}.version is required once status is ready/published")
    return errors


def check_plan(where, label, row, variants) -> list[str]:
    """status / version / variants / tags rules shared by defaults and products."""
    errors = []
    if "status" in row and row.get("status") not in STATUSES:
        errors.append(f"{where}: {label}.status must be one of {', '.join(STATUSES)}")
    errors += check_version(where, label, row)
    if "variants" in row:
        names = row["variants"]
        if not isinstance(names, list) or not names:
            errors.append(f"{where}: {label}.variants must be a non-empty list")
        else:
            errors += [f"{where}: {label}.variants lists unknown variant '{n}'" for n in names if n not in variants]
    if "tags" in row:
        tags = row["tags"]
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            errors.append(f"{where}: {label}.tags must be a list of strings")
    if "sync" in row:
        errors.append(f"{where}: {label}.sync is not a field{OLD_SECTION_HINTS['sync']}")
    return errors


def check_part_settings(where, label, name, settings) -> list[str]:
    if not isinstance(settings, dict):
        return [f"{where}: {label}: settings for '{name}' must be a mapping"]
    allowed = TOC_SETTINGS if name == "toc" else TERMS_SETTINGS if name == "terms" else PART_SETTINGS
    errors = []
    for k, v in settings.items():
        want = allowed.get(k)
        if want is None:
            errors.append(f"{where}: {label}: '{name}' has no setting '{k}' ({', '.join(allowed)})")
        elif not isinstance(v, want) or (want is int and isinstance(v, bool)):
            errors.append(f"{where}: {label}: {name}.{k} must be {want.__name__}")
    return errors


def check_parts(where, label, parts, *, grp, names, in_recipe) -> tuple[list[str], set[str], set[str]]:
    """Returns (errors, names used, names given a style)."""
    if not isinstance(parts, list) or not parts:
        return [f"{where}: {label} must list parts (e.g. [cover, intro, terms])"], set(), set()
    errors, used, styled = [], set(), set()
    for entry in parts:
        if isinstance(entry, dict):
            if len(entry) != 1:
                errors.append(f"{where}: {label}: a settings entry is one name mapped to its settings")
                continue
            ((name, settings),) = entry.items()
            name = str(name)
            errors += check_part_settings(where, label, name, settings or {})
            if isinstance(settings, dict) and settings.get("style"):
                styled.add(name)
        elif isinstance(entry, str):
            name = entry
        else:
            errors.append(f"{where}: {label}: {entry!r} is not a part name")
            continue
        if "$name" in name:
            if not in_recipe:
                errors.append(f"{where}: {label}: '$name' only makes sense inside a recipe")
            continue
        used.add(name)
        if name in GENERATED or name in grp or name in names:
            continue
        errors.append(f"{where}: {label} names '{name}' but it is not toc, terms, a group or a content file")
    return errors, used, styled


def check_rendering(where, cfg, templates) -> tuple[list[str], set[str]]:
    errors = []
    vy = f"{where}: rendering"
    if not isinstance(cfg, dict) or not cfg:
        return [f"{vy} is missing (default, variants, bundles)"], set()
    errors += [
        f"{vy}.{k} is not a rendering field (default, variants, bundles)"
        for k in cfg
        if k not in ("default", "variants", "bundles", "products")
    ]
    variants = cfg.get("variants") or {}
    if not isinstance(variants, dict) or not variants:
        return [f"{vy}.variants must map names to {{renderer, size, palette}}"], set()
    if cfg.get("default") not in variants:
        errors.append(f"{vy}.default must name one of the variants")
    for name, v in variants.items():
        v = v or {}
        renderer = v.get("renderer", "pdf")
        if renderer not in ("pdf", "epub"):
            errors.append(f"{vy}.variants.{name}.renderer must be pdf or epub (got {renderer!r})")
            continue
        if renderer == "epub":
            if v.get("size"):
                errors.append(f"{vy}.variants.{name}: 'size' does not apply to an epub variant")
            if not (templates / "epub.css").exists():
                errors.append(f"{vy}.variants.{name} renders epub but templates/epub.css is missing")
        for axis, folder in (("size", "sizes"), ("palette", "palettes")):
            value = v.get(axis)
            if not value:
                if renderer == "pdf":
                    errors.append(f"{vy}.variants.{name}.{axis} is missing")
            elif not (templates / folder / f"{value}.css").exists():
                errors.append(f"{vy}.variants.{name}.{axis} '{value}' has no templates/{folder}/{value}.css")
    for bundle, ns in (cfg.get("bundles") or cfg.get("products") or {}).items():
        for n in ns or []:
            if n not in variants:
                errors.append(f"{vy}.bundles.{bundle} lists unknown variant '{n}'")
    return errors, set(variants)


# ---------- one catalog ----------


def check_catalog(project: Project, path, name, names) -> tuple[list[str], list[str], set[str], set[str]]:
    """(errors, warnings, content names used, content names styled) for one catalog."""
    where = path
    errors, warnings = [], []
    cat = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(cat, dict):
        return [f"{where}: must be a mapping"], warnings, set(), set()
    for key in cat:
        if key not in SECTIONS:
            errors.append(
                f"{where}: '{key}' is not a catalog section ({', '.join(SECTIONS)}){OLD_SECTION_HINTS.get(key, '')}"
            )
    templates = project.templates
    e, variants = check_rendering(where, cat.get("rendering"), templates)
    errors += e
    defaults = cat.get("defaults") or {}
    if not isinstance(defaults, dict):
        errors.append(f"{where}: 'defaults' must be a mapping (variants, tags)")
        defaults = {}
    errors += [
        f"{where}: defaults.{k} is not a default (variants, tags)"
        for k in defaults
        if k not in ("variants", "tags", "sync")
    ]
    errors += check_plan(where, "defaults", defaults, variants)
    if "strings" in cat and not isinstance(cat["strings"], dict):
        errors.append(f"{where}: 'strings' must be a mapping of labels")
    terms = cat.get("terms") or {}
    if not isinstance(terms, dict) or any(k != "columns" for k in terms):
        errors.append(f"{where}: 'terms' takes only `columns: {{term|literal|meaning|example: [headers]}}`")
    else:
        for role, aliases in (terms.get("columns") or {}).items():
            if role not in ("term", "literal", "meaning", "example") or not isinstance(aliases, list):
                errors.append(
                    f"{where}: terms.columns.{role} must be one of term, literal, meaning, example "
                    f"mapped to a list of header words"
                )
    grp = cat.get("groups") or {}
    if not isinstance(grp, dict):
        errors.append(f"{where}: 'groups' must map group names to lists of content names")
        grp = {}
    prods = cat.get("products")
    for g, members in grp.items():
        if g in GENERATED or g in names or (isinstance(prods, dict) and g in prods):
            errors.append(f"{where}: groups.{g} shares its name with a generated part, a content file or a product")
        if not isinstance(members, list) or not members:
            errors.append(f"{where}: groups.{g} must be a non-empty list of content names")
            continue
        errors += [f"{where}: groups.{g} lists '{m}', which is not a content file" for m in members if m not in names]
    recs = cat.get("recipes") or {}
    if not isinstance(recs, dict):
        errors.append(f"{where}: 'recipes' must map recipe names to {{theme, parts}}")
        recs = {}
    for r, spec in recs.items():
        if not isinstance(spec, dict):
            errors.append(f"{where}: recipes.{r} must be a mapping (theme, parts)")
            continue
        errors += [
            f"{where}: recipes.{r}.{k} is not a recipe field (theme, parts)"
            for k in spec
            if k not in ("theme", "parts")
        ]
        e, _, _ = check_parts(where, f"recipes.{r}.parts", spec.get("parts"), grp=grp, names=names, in_recipe=True)
        errors += e
        theme = spec.get("theme", DEFAULT_THEME)
        if not (templates / f"{theme}.html").exists():
            errors.append(f"{where}: recipes.{r}.theme '{theme}' has no templates/{theme}.html")
    used, styled = set(), set()
    if not isinstance(prods, dict) or not prods:
        errors.append(f"{where}: 'products' must map product names to {{recipe | theme + parts, status, …}}")
        prods = {}
    for product, spec in prods.items():
        label = f"products.{product}"
        if not isinstance(spec, dict):
            errors.append(f"{where}: {label} must be a mapping")
            continue
        if "." in product or "/" in product:
            errors.append(f"{where}: {label}: a product name may not contain '.' or '/'")
        errors += [
            f"{where}: {label}.{k} is not a product field ({', '.join(PRODUCT_KEYS)})"
            for k in spec
            if k not in PRODUCT_KEYS and k != "sync"
        ]
        recipe = recs.get(spec.get("recipe")) if spec.get("recipe") else None
        if spec.get("recipe") and recipe is None:
            errors.append(f"{where}: {label}.recipe '{spec['recipe']}' is not a recipe")
            recipe = {}
        parts = spec.get("parts", (recipe or {}).get("parts"))
        if "parts" in spec and isinstance(parts, list):
            for entry in parts:
                n = next(iter(entry)) if isinstance(entry, dict) and entry else entry
                if isinstance(n, str) and "$name" in n:
                    errors.append(f"{where}: {label}.parts: '$name' only makes sense inside a recipe")
        resolved = [substitute(p, product) for p in parts] if isinstance(parts, list) else parts
        e, u, st = check_parts(where, f"{label}.parts", resolved, grp=grp, names=names, in_recipe=False)
        errors += e
        styled |= st
        for n in u:
            used.add(n)
            used |= set(grp.get(n) or [])
        theme = spec.get("theme", (recipe or {}).get("theme", DEFAULT_THEME))
        if not (templates / f"{theme}.html").exists():
            errors.append(f"{where}: {label}.theme '{theme}' has no templates/{theme}.html")
        errors += check_plan(where, label, spec, variants)
    return errors, warnings, used, styled


# ---------- run ----------


def run(project: Project) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    names = set(project.content_names())
    if project.content.exists():
        for p in project.content.rglob("*"):
            rel = p.relative_to(project.content)
            if p.is_dir() or any(part.startswith(".") for part in rel.parts):
                continue
            if p.suffix != ".md":
                errors.append(f"{p}: not a content file (content files are named <name>.md)")
    catalog_files = sorted(p for p in project.root.glob("catalog.*.yaml") if CATALOG_FILE.match(p.name))
    if not catalog_files:
        return [f"{project.root / 'catalog.<name>.yaml'}: no catalog found"], warnings
    used, styled = set(), set()
    for path in catalog_files:
        name = CATALOG_FILE.match(path.name).group(1)
        e, w, u, st = check_catalog(project, path, name, names)
        errors += e
        warnings += w
        used |= u
        styled |= st
    for n in sorted(names - used):
        warnings.append(f"content/{n}.md: no product in any catalog uses it")
    for n in sorted(names):
        p = project.content_path(n)
        if content.is_placeholder(p):
            continue
        e, w = check_body(p, styled=n in styled)
        errors += e
        warnings += w
    return errors, warnings
