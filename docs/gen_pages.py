"""Generate the pages that must not drift from the code (run by mkdocs-gen-files).

index.md      README.md, with repo-relative links pointed at the site's pages
changelog.md  CHANGELOG.md as it is
cli.md        `imprenta <command> --help` for every subcommand, from the real parser
"""

import argparse
from pathlib import Path

import mkdocs_gen_files

from imprenta.cli import build_parser

root = Path(__file__).resolve().parents[1]

readme = (root / "README.md").read_text(encoding="utf-8")
readme = readme.replace("](CHANGELOG.md)", "](changelog.md)").replace("](LICENSE)", "](https://github.com/jmcmeen/imprenta/blob/main/LICENSE)")
with mkdocs_gen_files.open("index.md", "w") as f:
    f.write(readme)

with mkdocs_gen_files.open("changelog.md", "w") as f:
    f.write((root / "CHANGELOG.md").read_text(encoding="utf-8"))

parser = build_parser()
subparsers = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
with mkdocs_gen_files.open("cli.md", "w") as f:
    f.write("# Command line\n\n")
    f.write("The `imprenta` command is a thin layer over `imprenta.Project`. A *spec* is\n")
    f.write("`<catalog>`, `<product>` or `<catalog>/<product>`, each optionally `.<variant>`.\n")
    f.write("This page is the parser's own help, rendered at build time.\n\n")
    f.write("```text\n" + parser.format_help().rstrip() + "\n```\n")
    for name, sub in subparsers.choices.items():
        f.write(f"\n## `imprenta {name}`\n\n")
        f.write("```text\n" + sub.format_help().rstrip() + "\n```\n")
