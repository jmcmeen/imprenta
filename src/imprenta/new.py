"""`imprenta new`: write the starter project.

The starter ships inside the package (`data/starter/`): a catalog, lorem ipsum
content with term tables, a theme, the Makefile, the Node pin for pagedjs-cli
and a check workflow. It is the project the engine's own tests exercise, so it
is always set up for the engine that writes it, and the pin it writes is that
engine's version. Entries named `dot-<name>` become `.<name>` on the way out,
so the package carries no dotfiles of its own.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from importlib.resources import files
from pathlib import Path

from . import __version__

TEMPLATED = ("pyproject.toml", "package.json", "README.md", "CLAUDE.md")
DOT = "dot-"
RELEASE = re.compile(r"\d+(\.\d+){1,2}$")  # X.Y or X.Y.Z: what goes after `==` in the pin


def starter_dir() -> Path:
    return Path(str(files("imprenta").joinpath("data", "starter")))


def pin_version(version: str = __version__) -> str:
    """The release to pin: the public X.Y.Z of the running engine (a dev build pins its base)."""
    m = re.match(r"\d+(\.\d+){1,2}", version)
    return m.group(0) if m else version


def scaffold(dest: Path | str, name: str | None = None, version: str | None = None) -> Path:
    """Write the starter into `dest` (missing or empty). Returns the destination.

    The pin must be a release number, since it lands verbatim after `==` in the
    generated pyproject.toml. The copy is made beside `dest` and moved into place
    when complete, so a failure leaves nothing half-written there.
    """
    dest = Path(dest)
    if dest.exists() and not dest.is_dir():
        raise FileExistsError(f"{dest} exists and is not a folder")
    if dest.is_dir() and any(dest.iterdir()):
        raise FileExistsError(f"{dest} exists and is not empty")
    name = name or dest.resolve().name
    version = version or pin_version()
    if not RELEASE.fullmatch(version):
        raise ValueError(f"not a release number: {version!r} (expected X.Y.Z)")
    dest.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=f".{dest.name}-", dir=dest.parent))
    try:
        _copy(starter_dir(), work, {"{{name}}": name, "{{version}}": version})
        if dest.is_dir():
            dest.rmdir()  # empty, checked above
        work.rename(dest)
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise
    return dest


def _copy(src: Path, dst: Path, subs: dict[str, str]) -> None:
    for entry in sorted(src.iterdir()):
        if entry.name == "__pycache__":
            continue
        out = dst / (f".{entry.name[len(DOT) :]}" if entry.name.startswith(DOT) else entry.name)
        if entry.is_dir():
            out.mkdir()
            _copy(entry, out, subs)
        elif entry.name in TEMPLATED:
            text = entry.read_text(encoding="utf-8")
            for key, value in subs.items():
                text = text.replace(key, value)
            out.write_text(text, encoding="utf-8")
        else:
            shutil.copy2(entry, out)
