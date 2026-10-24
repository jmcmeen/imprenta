"""`imprenta new`: write the starter project.

The starter ships inside the package (`data/starter/`): a catalog, lorem ipsum
content with term tables, a theme, the Makefile, the Node pin for pagedjs-cli
and a check workflow. It is the project the engine's own tests exercise, so it
is always set up for the engine that writes it, and the pin it writes is that
engine's version. Entries named `dot-<name>` become `.<name>` on the way out,
so the package carries no dotfiles of its own.
"""

from __future__ import annotations

import os
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
    """Write the starter into `dest` (missing or empty, `.` included). Returns the destination.

    The pin must be a release number, since it lands verbatim after `==` in the
    generated pyproject.toml. The copy is made beside `dest` and moved into place
    when complete, so a failure leaves nothing half-written there, not even
    parent folders this call created. A symlink is refused rather than replaced.
    """
    given = Path(dest)
    if given.is_symlink():
        raise FileExistsError(f"{given} is a symlink; give the folder itself")
    dest = given.absolute()
    if dest.exists() and not dest.is_dir():
        raise FileExistsError(f"{given} exists and is not a folder")
    existed = dest.is_dir()
    if existed and any(dest.iterdir()):
        raise FileExistsError(f"{given} exists and is not empty")
    name = name or dest.name
    version = version or pin_version()
    if not RELEASE.fullmatch(version):
        raise ValueError(f"not a release number: {version!r} (expected X.Y.Z)")
    created = _mkdirs(dest.parent)
    work = Path(tempfile.mkdtemp(prefix=f".{dest.name}-", dir=dest.parent))
    try:
        _copy(starter_dir(), work, {"{{name}}": name, "{{version}}": version})
        _move_into_place(work, dest, given, existed)
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        for folder in reversed(created):
            try:
                folder.rmdir()
            except OSError:
                pass
        raise
    return dest


def _mkdirs(folder: Path) -> list[Path]:
    """mkdir -p, returning the folders this call created (outermost first)."""
    missing = []
    while not folder.exists():
        missing.append(folder)
        folder = folder.parent
    for f in reversed(missing):
        f.mkdir()
    return list(reversed(missing))


def _move_into_place(work: Path, dest: Path, given: Path, existed: bool) -> None:
    """Rename the staged tree to `dest`; one that already existed empty (maybe the cwd) is filled entry by entry.

    If something else took `dest` during the copy, the rename onto it fails (or it is no
    longer empty); either is reported as the destination being taken, the same as if it
    had been so from the start.
    """
    try:
        if not existed:
            work.rename(dest)  # fails if dest appeared meanwhile
            return
        if any(dest.iterdir()):
            raise FileExistsError
        for entry in list(work.iterdir()):
            os.rename(entry, dest / entry.name)
        work.rmdir()
    except OSError as e:
        raise FileExistsError(f"{given} exists and is not empty") from e


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
