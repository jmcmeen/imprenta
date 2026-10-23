"""imprenta: a content arranger and styler.

Markdown files in `content/` are arranged into products (PDFs, EPUBs) by one or
more `catalog.<name>.yaml` files. The engine knows content, parts, groups,
recipes, products, themes and render variants, and nothing about what the
content is about or what language it is in.

    from imprenta import Project

    project = Project.find()               # the repo that holds catalog.*.yaml
    for target in project.targets():       # (catalog, product, variant)
        project.build(target)
    errors, warnings = project.check()

The command line (`imprenta build|check|status|affected|doctor|manager`) and
the manager TUI (`pip install imprenta[tui]`) are thin layers over Project.
"""

from importlib.metadata import PackageNotFoundError, version

from .catalog import Catalog
from .project import Project
from .targets import Target

try:
    __version__ = version("imprenta")
except PackageNotFoundError:  # running from a checkout that is not installed
    __version__ = "0.0.0"

__all__ = ["Catalog", "Project", "Target", "__version__"]
