"""Building one target: freshness, assembly, pandoc, Paged.js, the stamp."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from . import parts, render
from .catalog import GENERATED

if TYPE_CHECKING:
    from .project import Project
    from .targets import Target


class BuildError(RuntimeError):
    pass


# ---------- freshness ----------


def is_fresh(target: Path, inputs, stamp: str | None = None, tmp: Path | None = None) -> bool:
    """True if `target` exists, is newer than every input path, and (when a
    `stamp` is given) was last built from the same catalog rows and engine
    version. The stamp lives in tmp/, so editing one product's line never
    makes every other output stale."""
    if not target.exists():
        return False
    mtime = target.stat().st_mtime
    if not all(p.stat().st_mtime <= mtime for p in inputs if p.exists()):
        return False
    return stamp is None or read_stamp(target, tmp) == stamp


def stamp_path(target: Path, tmp: Path | None) -> Path:
    return (tmp or target.parent) / f"{target.name}.stamp"


def read_stamp(target: Path, tmp: Path | None) -> str | None:
    p = stamp_path(target, tmp)
    return p.read_text(encoding="utf-8") if p.exists() else None


def write_stamp(target: Path, stamp: str, tmp: Path | None) -> None:
    p = stamp_path(target, tmp)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(stamp, encoding="utf-8")


def row_stamp(project: Project, target: Target) -> str:
    """The catalog rows a target renders from plus the engine version, serialized."""
    from . import __version__

    cat = project.catalog(target.catalog)
    row = cat.render_row(target.product, target.variant)
    row["imprenta"] = __version__
    return json.dumps(row, sort_keys=True, ensure_ascii=False, default=str)


def inputs(project: Project, target: Target) -> list[Path]:
    """File inputs of one target: its content files and the template-side files
    its variant uses (the catalog rows are covered by the stamp)."""
    cat = project.catalog(target.catalog)
    files = [project.content_path(n) for n, _ in cat.resolve_parts(target.product) if n not in GENERATED]
    templates = project.templates
    renderer = cat.variant_renderer(target.variant)
    if renderer == "pdf":
        files += [*templates.glob("*.html"), templates / "print.css"]
    else:
        files.append(templates / "epub.css")
    files += cat.variant_layers(target.variant)
    files += list((templates / "fonts").glob("*"))
    return files


# ---------- the build ----------


def build(
    project: Project, target: Target, *, pdf: bool = True, preview: bool = False, force: bool = False, log=print
) -> Path:
    """Build one target by arranging its parts. Returns the output path (the
    HTML path when `pdf` is False). Raises BuildError for a bad target."""
    cat = project.catalog(target.catalog)
    if not cat.data:
        raise BuildError(f"No catalog '{target.catalog}' (catalog.{target.catalog}.yaml)")
    if target.product not in cat.products:
        raise BuildError(f"Unknown product '{target.product}' in catalog.{target.catalog}.yaml")
    variant = cat.resolve_variant(target.variant)
    renderer = cat.variant_renderer(variant)
    if renderer != "pdf" and (preview or not pdf):
        raise BuildError(f"Variant '{variant}' renders an EPUB; --html/--preview apply to pdf variants only.")
    out = cat.output_path(target.product, variant)
    stamp = row_stamp(project, target)
    if pdf and not force and is_fresh(out, inputs(project, target), stamp, project.tmp):
        log(f"Up to date: {project.rel(out)}")
        return out

    files, names = parts.assemble(cat, target.product, project.tmp)
    if not files:
        raise BuildError(f"{target.catalog}/{target.product}: nothing to assemble (none of its parts exist)")
    log(f"{target.catalog}/{target.product} [{variant}]: {len(files)} parts")
    meta = {
        "title": parts.page_title(cat, target.product),
        "lang": parts.page_lang(cat, target.product),
        "edition": cat.plan(target.product).get("version"),
        "date": render.build_date(),
    }
    common = ["--strip-comments", "--lua-filter", str(render.toc_filter()), *map(str, files)]
    if renderer == "epub":
        out.parent.mkdir(parents=True, exist_ok=True)
        render.pandoc(
            project.root,
            [
                *common,
                *render.epub_args(cat, variant),
                *render.meta_args(meta, "title", "lang", "date"),
                "-o",
                str(out),
            ],
        )
        write_stamp(out, stamp, project.tmp)
        log(f"Built {project.rel(out)}")
        return out
    render.copy_assets(project)
    html = project.tmp / f"{target.product}.{target.catalog}.{variant}.html"
    common_meta = {"version": render.git_version(project.root), "date": meta["date"], **cat.variant_meta(variant)}
    if preview:
        common_meta.update(preview="true", polyfill=render.polyfill_src(project))
    render.pandoc(
        project.root,
        [
            *common,
            "--template",
            str(project.theme_template(cat.theme(target.product))),
            *render.meta_args(meta, "title", "lang", "edition"),
            *render.meta_args(
                common_meta,
                "version",
                "date",
                "preview",
                "polyfill",
                "variant",
                "size",
                "palette",
                "size_css",
                "palette_css",
            ),
            "-o",
            str(html),
        ],
    )
    if not pdf:
        log(f"Wrote {project.rel(html)}")
        return html
    render.render_pdf(project, html, out)
    write_stamp(out, stamp, project.tmp)
    log(f"Built {project.rel(out)}")
    return out
