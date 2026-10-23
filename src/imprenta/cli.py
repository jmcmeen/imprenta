"""The command line: a thin layer over Project.

    imprenta build [spec …] [--force] [--jobs N] [--tag T] [--html | --preview]
    imprenta check
    imprenta status
    imprenta affected [--since COMMIT] [--tag T] [--variant V | --bundle B] [--all]
    imprenta doctor
    imprenta manager
    imprenta version

A spec is <catalog>, <product>, <catalog>/<product>, optionally .<variant>.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .build import BuildError
from .project import Project, ProjectNotFound
from .targets import SpecError, Target


def project_or_exit() -> Project:
    try:
        return Project.find()
    except ProjectNotFound as e:
        sys.exit(str(e))


def cmd_build(args) -> int:
    project = project_or_exit()
    try:
        if args.spec:
            targets: list[Target] = []
            for spec in args.spec:
                targets += project.spec_targets(spec)
        else:
            targets = project.targets(tag=args.tag)
        if args.tag and args.spec:
            targets = [t for t in targets if args.tag in project.catalog(t.catalog).plan(t.product)["tags"]]
        if args.html or args.preview:
            if len(targets) != 1:
                sys.exit("--html / --preview build exactly one target: name a product and, if needed, a variant")
            out = project.build(targets[0], pdf=False, preview=args.preview, force=True)
            print(f"Wrote {project.rel(out)}")
            return 0
        project.build_many(targets, force=args.force, jobs=args.jobs)
    except (SpecError, BuildError, KeyError, FileNotFoundError) as e:
        sys.exit(str(e))
    print(f"Built {len(targets)} file(s).")
    return 0


def cmd_check(args) -> int:
    project = project_or_exit()
    errors, warnings = project.check()
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}")
    n_products = sum(len(c.products) for c in project.catalogs().values())
    print(
        f"checked {len(project.content_names())} content files and {n_products} products: "
        f"{len(errors)} errors, {len(warnings)} warnings"
    )
    return 1 if errors else 0


def cmd_status(args) -> int:
    project = project_or_exit()
    for name, cat in project.catalogs().items():
        print(f"catalog {name}: {len(cat.products)} products")
        for product in cat.products:
            plan = cat.plan(product)
            n = len(cat.resolve_parts(product))
            tags = ",".join(plan["tags"])
            print(
                f"  {product:20} {plan['status'] or '-':<10} v{plan['version'] or '-':<5} "
                f"{','.join(plan['variants']):<24} {tags:<12} {n:>3} parts {project.product_words(cat, product):>7}w"
            )
        default = cat.default_variant
        names = [f"{v}{' (default)' if v == default else ''}" for v in sorted(cat.variants)]
        print(f"  variants: {', '.join(names) or 'none'}")
    return 0


def cmd_affected(args) -> int:
    project = project_or_exit()
    only = None
    if args.variant or args.bundle:
        first = project.catalog(project.catalog_names()[0])
        try:
            only = first.variant_filter(args.variant, args.bundle)
        except KeyError as e:
            sys.exit(str(e))
    for t in project.targets_since(None if args.all else args.since, only, args.tag):
        print(t)
    return 0


def cmd_doctor(args) -> int:
    project = project_or_exit()
    ok = True
    for name, found, hint in project.doctor():
        print(f"{'ok  ' if found else 'MISSING'} {name:16} {found or hint}")
        ok = ok and bool(found)
    if ok:
        print("All build tools found.")
    return 0 if ok else 1


def cmd_manager(args) -> int:
    try:
        from .tui import Manager
    except ImportError:
        sys.exit("The manager needs the TUI extra: pip install 'imprenta[tui]'  (or: uv add 'imprenta[tui]')")
    Manager(project_or_exit()).run()
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="imprenta", description="Arrange content into products and render them.")
    sub = ap.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="build targets: specs, or everything the catalogs subscribe")
    b.add_argument("spec", nargs="*", help="<catalog> | <product> | <catalog>/<product>, each optionally .<variant>")
    b.add_argument("--tag", help="only products carrying this tag")
    b.add_argument("--force", action="store_true", help="rebuild even if up to date")
    b.add_argument("--jobs", type=int, default=os.cpu_count() or 2)
    b.add_argument("--html", action="store_true", help="stop after HTML (one pdf target)")
    b.add_argument("--preview", action="store_true", help="HTML with the Paged.js polyfill for a live browser preview")
    b.set_defaults(fn=cmd_build)

    sub.add_parser("check", help="validate content and catalogs").set_defaults(fn=cmd_check)
    sub.add_parser("status", help="list every product of every catalog").set_defaults(fn=cmd_status)

    af = sub.add_parser("affected", help="list the targets a change set since a commit affects")
    af.add_argument("--since", help="the commit to diff against (omit = everything)")
    af.add_argument("--all", action="store_true", help="ignore --since: everything")
    af.add_argument("--tag", help="only products carrying this tag")
    af.add_argument("--variant", help="limit to one variant")
    af.add_argument("--bundle", help="limit to one bundle's variants")
    af.set_defaults(fn=cmd_affected)

    sub.add_parser("doctor", help="check that every external tool is installed").set_defaults(fn=cmd_doctor)
    sub.add_parser("manager", help="the TUI (needs imprenta[tui])").set_defaults(fn=cmd_manager)
    sub.add_parser("version", help="print the version").set_defaults(fn=lambda a: print(__version__) or 0)

    args = ap.parse_args(argv)
    return args.fn(args)
