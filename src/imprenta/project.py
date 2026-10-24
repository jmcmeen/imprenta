"""The project: a folder holding content/, templates/ and one or more catalogs.

project = Project.find()                 # walk up from the cwd to the catalogs
project.catalogs()                       # {name: Catalog}
project.targets(tag="release")           # [(catalog, product, variant), …]
project.build(target)                    # -> output path
project.check()                          # -> (errors, warnings)
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from . import content
from .catalog import Catalog
from .targets import CATALOG_FILE, Target, affected_targets, all_targets, catalogs_at, changed_since, spec_targets


class ProjectNotFound(FileNotFoundError):
    pass


class Project:
    """A folder holding `content/`, `templates/` and one or more `catalog.<name>.yaml`.

    Everything the command line and the manager do goes through one of these:
    find the catalogs, list targets, build them, check the rules.
    """

    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        self.content = self.root / "content"
        self.templates = self.root / "templates"
        self.output = self.root / "output"
        self.tmp = self.root / "tmp"
        self._cache: dict[str, tuple[int, Catalog]] = {}

    def __repr__(self) -> str:
        return f"Project({str(self.root)!r})"

    @classmethod
    def find(cls, start: Path | str | None = None) -> Project:
        """The nearest ancestor of `start` (default: the cwd) holding a catalog.*.yaml."""
        here = Path(start or os.getcwd()).resolve()
        for folder in (here, *here.parents):
            if any(CATALOG_FILE.match(p.name) for p in folder.glob("catalog.*.yaml")):
                return cls(folder)
        raise ProjectNotFound(f"No catalog.<name>.yaml found in {here} or any parent folder")

    def rel(self, path: Path) -> str:
        """A path relative to the project root when it is inside it, else as given."""
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)

    # ----- catalogs -----

    def catalog_path(self, name: str) -> Path:
        """Where `catalog.<name>.yaml` lives, whether or not it exists."""
        return self.root / f"catalog.{name}.yaml"

    def catalog_names(self) -> list[str]:
        """The `<name>` of every `catalog.<name>.yaml` in the root, sorted."""
        return sorted(m.group(1) for p in self.root.glob("catalog.*.yaml") if (m := CATALOG_FILE.match(p.name)))

    def catalog(self, name: str) -> Catalog:
        """One catalog, parsed (cached on the file's mtime); empty if absent."""
        path = self.catalog_path(name)
        if not path.exists():
            return Catalog(self, name, {})
        stamp = path.stat().st_mtime_ns
        hit = self._cache.get(name)
        if hit and hit[0] == stamp:
            return hit[1]
        cat = Catalog(self, name, yaml.safe_load(path.read_text(encoding="utf-8")) or {})
        self._cache[name] = (stamp, cat)
        return cat

    def catalogs(self) -> dict[str, Catalog]:
        """Every catalog, parsed, by name."""
        return {n: self.catalog(n) for n in self.catalog_names()}

    # ----- content -----

    def content_path(self, name: str) -> Path:
        """Where a content file lives; a name is its path under content/ without .md."""
        return self.content / f"{name}.md"

    def content_names(self) -> list[str]:
        """Every content file's name, sorted (hidden folders such as .obsidian/ skipped)."""
        out = []
        if not self.content.exists():
            return out
        for p in self.content.rglob("*.md"):
            rel = p.relative_to(self.content)
            if any(part.startswith(".") for part in rel.parts):
                continue
            out.append(str(rel.with_suffix("")).replace("\\", "/"))
        return sorted(out)

    def content_label(self, name: str) -> str:
        """The short name a glossary prints for a content file: its `label`, or one derived from the name."""
        return str(content.read_meta(self.content_path(name)).get("label") or content.default_label(name))

    def word_count(self, name: str) -> int:
        """Words in a content file's prose, ignoring front matter and author notes."""
        return content.word_count(self.content_path(name))

    def product_words(self, cat: Catalog, product: str) -> int:
        """Words across every content file a product's parts resolve to."""
        return sum(self.word_count(n) for n in cat.content_names(product))

    def theme_template(self, theme: str) -> Path:
        """`templates/<theme>.html`; raises FileNotFoundError if the theme has none."""
        path = self.templates / f"{theme}.html"
        if not path.exists():
            raise FileNotFoundError(f"Theme '{theme}' has no {self.rel(path)}")
        return path

    # ----- targets -----

    def targets(self, only=None, tag: str | None = None) -> list[Target]:
        """Every target the catalogs subscribe, narrowed by a variant filter and/or a tag."""
        return all_targets(self.catalogs(), only, tag)

    def targets_since(self, commit: str | None, only=None, tag: str | None = None) -> list[Target]:
        """Targets a change set since `commit` affects; everything if the commit is unknown."""
        cats = self.catalogs()
        changed = changed_since(self.root, commit)
        if changed is None:
            return all_targets(cats, only, tag)
        return affected_targets(changed, cats, only, tag, old_cats=catalogs_at(self, commit))

    def affected(self, changed, only=None, tag=None, old_cats=None) -> list[Target]:
        """Targets a set of changed paths affects, judged against the current catalogs (and `old_cats`, if given)."""
        return affected_targets(changed, self.catalogs(), only, tag, old_cats)

    def spec_targets(self, spec: str) -> list[Target]:
        """Targets a spec names: `<catalog>`, `<product>` or `<catalog>/<product>`, each optionally `.<variant>`."""
        return spec_targets(self, spec)

    # ----- building -----

    def build(self, target: Target, *, pdf=True, preview=False, force=False, log=print) -> Path:
        """Build one target and return its output path; skipped when up to date unless `force`.

        `pdf=False` stops at the HTML; `preview` adds the Paged.js polyfill to it for a live browser preview.
        """
        from .build import build

        return build(self, Target(*target), pdf=pdf, preview=preview, force=force, log=log)

    def build_many(self, targets, *, force=False, jobs: int | None = None, log=print) -> list[Path]:
        """Build several targets in parallel; returns their output paths in order."""
        jobs = jobs or os.cpu_count() or 2
        with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
            return list(pool.map(lambda t: self.build(t, force=force, log=log), targets))

    # ----- checks -----

    def check(self) -> tuple[list[str], list[str]]:
        """Validate content and catalogs against the rules: `(errors, warnings)`, each a list of messages."""
        from .check import run

        return run(self)

    def doctor(self):
        """`[(tool, where it was found or None, how to get it)]` for every external tool.

        Pandoc, node, pagedjs-cli, Chrome or Chromium, and the theme fonts.
        """
        from .render import doctor

        return doctor(self)
