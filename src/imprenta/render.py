"""Rendering: pandoc for HTML and EPUB, pagedjs-cli (Paged.js in headless
Chrome) for PDF. These are external tools a content repo installs itself;
`doctor()` says which are missing."""

from __future__ import annotations

import datetime as dt
import os
import platform
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .catalog import Catalog
    from .project import Project

POLYFILL_CDN = "https://unpkg.com/pagedjs@0.4.3/dist/paged.polyfill.js"


def toc_filter() -> Path:
    """The packaged pandoc Lua filter that renders `toc` markers."""
    return Path(str(files("imprenta").joinpath("data", "toc.lua")))


def build_date() -> str:
    return dt.date.today().isoformat()


def git_version(root: Path) -> str:
    """`git describe` output (tags, else short sha, '-dirty' if modified)."""
    try:
        out = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unversioned"


# ---------- toolchain ----------


def pagedjs_cli(project: Project) -> str | None:
    """Prefer the version the content repo pins in package.json; fall back to a global install."""
    local = project.root / "node_modules" / ".bin" / "pagedjs-cli"
    if local.exists():
        return str(local)
    return shutil.which("pagedjs-cli")


def polyfill_local(project: Project) -> Path:
    return project.root / "node_modules" / "pagedjs" / "dist" / "paged.polyfill.js"


def find_chrome() -> str | None:
    """The Chrome/Chromium binary pagedjs-cli should drive, or None."""
    if os.environ.get("PUPPETEER_EXECUTABLE_PATH"):
        return os.environ["PUPPETEER_EXECUTABLE_PATH"]
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        path = shutil.which(name)
        if path:
            return path
    if platform.system() == "Darwin":
        for mac in (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ):
            if Path(mac).exists():
                return mac
    return None


def chrome_env() -> dict:
    """pagedjs-cli renders via puppeteer-core, which does NOT bundle Chromium."""
    env = os.environ.copy()
    chrome = find_chrome()
    if chrome:
        env["PUPPETEER_EXECUTABLE_PATH"] = chrome
    return env


def doctor(project: Project) -> list[tuple[str, str | None, str]]:
    """[(tool, where it was found or None, how to get it)] for every external tool."""
    fonts = project.templates / "fonts" / "fonts.css"
    return [
        ("pandoc", shutil.which("pandoc"), "brew install pandoc / apt-get install pandoc"),
        ("node", shutil.which("node"), "brew install node / apt-get install nodejs npm"),
        ("pagedjs-cli", pagedjs_cli(project), "npm install  (pin pagedjs-cli in package.json)"),
        ("Chrome/Chromium", find_chrome(), "install Chrome, or export PUPPETEER_EXECUTABLE_PATH"),
        ("theme fonts", str(fonts) if fonts.exists() else None, f"put fonts.css in {project.templates / 'fonts'}"),
    ]


# ---------- pandoc and Paged.js ----------


def pandoc(root: Path, args: list[str]) -> None:
    subprocess.run(["pandoc", *args], check=True, cwd=root)


def meta_args(flat: dict, *keys: str) -> list[str]:
    """Selected flat-metadata fields as pandoc --metadata key=value arguments."""
    args: list[str] = []
    for k in keys:
        v = flat.get(k)
        if v not in (None, ""):
            args += ["--metadata", f"{k}={v}"]
    return args


def copy_assets(project: Project) -> None:
    """Put print.css, the fonts and the layers next to the generated HTML so links resolve."""
    tmp, templates = project.tmp, project.templates
    tmp.mkdir(parents=True, exist_ok=True)
    if (templates / "print.css").exists():
        shutil.copy(templates / "print.css", tmp / "print.css")
    for sub in ("fonts", "sizes", "palettes"):
        if (templates / sub).exists():
            shutil.copytree(templates / sub, tmp / sub, dirs_exist_ok=True)
    if polyfill_local(project).exists():
        shutil.copy(polyfill_local(project), tmp / "paged.polyfill.js")


def polyfill_src(project: Project) -> str:
    return "paged.polyfill.js" if polyfill_local(project).exists() else POLYFILL_CDN


def epub_fonts_css(project: Project) -> Path | None:
    """fonts.css rewritten for an EPUB, where embedded fonts live in ../fonts/."""
    src = project.templates / "fonts" / "fonts.css"
    if not src.exists():
        return None
    project.tmp.mkdir(parents=True, exist_ok=True)
    out = project.tmp / "epub-fonts.css"
    out.write_text(src.read_text(encoding="utf-8").replace("url('", "url('../fonts/"), encoding="utf-8")
    return out


def epub_args(cat: Catalog, variant: str) -> list[str]:
    """Pandoc flags for every EPUB: writer, stylesheets, embedded theme fonts, nav."""
    project = cat.project
    args = ["-t", "epub3", "--toc", "--toc-depth=2", "--epub-chapter-level=1"]
    fonts = epub_fonts_css(project)
    if fonts:
        args += ["--css", str(fonts)]
    if (project.templates / "epub.css").exists():
        args += ["--css", str(project.templates / "epub.css")]
    for layer in cat.variant_layers(variant):
        args += ["--css", str(layer)]
    for font in sorted((project.templates / "fonts").glob("*.woff2")):
        args += ["--epub-embed-font", str(font)]
    return args


def render_pdf(project: Project, html_path: Path, pdf_path: Path) -> None:
    """Paginate HTML and render to PDF with Paged.js (headless Chrome)."""
    cli = pagedjs_cli(project)
    if not cli:
        sys.exit("pagedjs-cli not found: install it with npm (see `imprenta doctor`).")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    # Extra Chrome flags, comma separated. CI needs --no-sandbox: Ubuntu 24.04
    # runners restrict unprivileged user namespaces, so Chrome's sandbox can't start.
    extra = os.environ.get("PAGEDJS_BROWSER_ARGS")
    subprocess.run(
        [cli, str(html_path), "-o", str(pdf_path), *(["--browserArgs", extra] if extra else [])],
        check=True,
        env=chrome_env(),
        cwd=project.root,
    )
