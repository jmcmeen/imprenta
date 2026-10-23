"""The manager: a terminal dashboard over a project's catalogs and outputs.

    imprenta manager            (pip install 'imprenta[tui]')

One row per product of every catalog, showing status, edition, tags, part
count, word count and when it was last built. Enter opens the product: its
parts, settings, outputs per variant, and controls (status, edition, variant
subscriptions, tags, build, open). Keys write the catalog through imprenta.edit
(comments survive), then run the check; builds stream into the log pane. Prose
is never edited here: `y` opens the catalog in $EDITOR.
"""

from __future__ import annotations

import datetime as dt
import os
import platform
import re
import shutil
import subprocess
import sys

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import DataTable, Footer, Header, Input, Label, RichLog, Static

from . import edit as ce
from .catalog import GENERATED
from .project import Project

COLUMNS = ("product", "catalog", "status", "edition", "tags", "parts", "words", "built")
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
MARKUP = re.compile(r"\[/?[a-z $#0-9]*\]")


# ---------- rows ----------


def age(mtime) -> str:
    if mtime is None:
        return "—"
    delta = dt.datetime.now() - dt.datetime.fromtimestamp(mtime)
    if delta.days:
        return f"{delta.days}d ago"
    hours, minutes = divmod(int(delta.total_seconds()) // 60, 60)
    return f"{hours}h ago" if hours else f"{minutes}m ago"


def human_size(n) -> str:
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def newest_output(project: Project, catname: str, product: str):
    """(path, mtime) of the most recent output for one product, or (None, None)."""
    cat = project.catalog(catname)
    paths = [cat.output_path(product, v) for v in cat.plan(product)["variants"] if v in cat.variants]
    paths = [p for p in paths if p.exists()]
    if not paths:
        return None, None
    best = max(paths, key=lambda p: p.stat().st_mtime)
    return best, best.stat().st_mtime


def rows(project: Project):
    """[(row_key, cells)]: every product of every catalog, in catalog order."""
    out = []
    for catname, cat in project.catalogs().items():
        for product in cat.products:
            plan = cat.plan(product)
            _, mtime = newest_output(project, catname, product)
            words = project.product_words(cat, product)
            out.append(
                (
                    f"{catname}|{product}",
                    (
                        product,
                        catname,
                        plan["status"] or "—",
                        plan["version"] or "—",
                        ",".join(plan["tags"]) or "·",
                        f"{len(cat.resolve_parts(product))}",
                        f"{words:,}" if words else "—",
                        age(mtime),
                    ),
                )
            )
    return out


def fmt_settings(settings) -> str:
    return " · ".join(f"{k}: {'off' if v is False else 'on' if v is True else v}" for k, v in settings.items())


def product_info(project: Project, catname: str, product: str) -> dict:
    """Everything the product screen shows, computed fresh from disk."""
    cat = project.catalog(catname)
    plan = cat.plan(product)
    resolved = {n for n, _ in cat.resolve_parts(product)}
    parts = []
    for name, settings in cat.part_entries(product):
        if name in cat.groups:
            members = cat.groups[name] or []
            missing = [m for m in members if not project.content_path(m).exists()]
            desc = f"group · {len(members)} files" + (f" · missing: {', '.join(missing)}" if missing else "")
            parts.append((name, desc, True))
        elif name in GENERATED:
            parts.append((name, "generated" + (f" · {fmt_settings(settings)}" if settings else ""), True))
        else:
            ok = name in resolved
            desc = f"{project.word_count(name):,} words" if ok else "MISSING FILE"
            if settings:
                desc += f" · {fmt_settings(settings)}"
            parts.append((name, desc, ok))
    outputs = []
    for v in cat.variants:
        path = cat.output_path(product, v)
        st = path.stat() if path.exists() else None
        outputs.append(
            (v, v in plan["variants"], path, age(st.st_mtime) if st else "—", human_size(st.st_size) if st else "—")
        )
    return {
        "catalog": catname,
        "product": product,
        "recipe": (cat.products.get(product) or {}).get("recipe"),
        "theme": cat.theme(product),
        "plan": plan,
        "parts": parts,
        "outputs": outputs,
        "words": project.product_words(cat, product),
        "variants": list(cat.variants),
    }


def git_summary(root) -> str:
    try:
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.splitlines()
        ab = subprocess.run(
            ["git", "rev-list", "--left-right", "--count", "HEAD...@{upstream}"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "git: ?"
    ahead, behind = (int(x) for x in ab) if len(ab) == 2 else (0, 0)
    bits = [f"{len(dirty)} changed" if dirty else "clean"]
    if ahead:
        bits.append(f"{ahead} to push")
    if behind:
        bits.append(f"{behind} to pull")
    return "git: " + ", ".join(bits)


def opener() -> str:
    return "open" if platform.system() == "Darwin" else "xdg-open"


# ---------- screens ----------


class TextScreen(ModalScreen):
    """Ask for one line of text; dismiss with it (None on escape)."""

    BINDINGS = [Binding("escape", "cancel", "cancel")]
    DEFAULT_CSS = """
    TextScreen { align: center middle; }
    TextScreen > Vertical { width: 80; height: auto; border: round $accent; padding: 1 2; background: $surface; }
    """

    def __init__(self, title: str, lines: list[str], placeholder: str):
        super().__init__()
        self.title_text, self.lines, self.placeholder = title, lines, placeholder

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.title_text)
            if self.lines:
                yield Static("\n".join(self.lines[:12]), classes="dim")
            yield Input(placeholder=self.placeholder)

    @on(Input.Submitted)
    def submit(self, event):
        self.dismiss(event.value.strip() or None)

    def action_cancel(self):
        self.dismiss(None)


class ProductScreen(Screen):
    """One product: its definition, parts, outputs and every control."""

    BINDINGS = [
        Binding("escape", "back", "back"),
        Binding("t", "cycle_status", "status"),
        Binding("v", "bump('minor')", "edition +.1"),
        Binding("V", "bump('major')", "edition +1"),
        Binding("a", "tag", "tag"),
        Binding("b", "build", "build"),
        Binding("o", "open_output", "open"),
        Binding("c", "check", "check"),
        Binding("y", "edit_catalog", "edit catalog"),
        *[Binding(str(i), f"toggle_variant({i})", f"variant {i}", show=i == 1) for i in range(1, 10)],
    ]
    DEFAULT_CSS = """
    ProductScreen VerticalScroll { height: 1fr; padding: 0 2; }
    ProductScreen .title { text-style: bold; color: $accent; margin-top: 1; }
    ProductScreen .block { margin-bottom: 1; }
    """

    def __init__(self, catname: str, product: str):
        super().__init__()
        self.catname, self.product = catname, product

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static(id="head", classes="block")
            yield Static("Publishing", classes="title")
            yield Static(id="plan", classes="block")
            yield Static("Variants  (press the number to subscribe / unsubscribe)", classes="title")
            yield Static(id="variants", classes="block")
            yield Static("Parts, in order", classes="title")
            yield Static(id="parts", classes="block")
        yield Footer()

    def on_mount(self):
        self.refresh_view()

    def refresh_view(self):
        info = product_info(self.app.project, self.catname, self.product)
        plan = info["plan"]
        self.sub_title = f"{self.catname}/{self.product}"
        self.query_one("#head", Static).update(
            f"[bold]{self.product}[/]  in catalog [bold]{self.catname}[/]"
            + (f"  ·  recipe [bold]{info['recipe']}[/]" if info["recipe"] else "")
            + f"  ·  theme [bold]{info['theme']}[/]  ·  {info['words']:,} words in {len(info['parts'])} parts"
        )
        self.query_one("#plan", Static).update(
            f"  [dim]t[/] status   {plan['status'] or '—'}\n"
            f"  [dim]v V[/] edition  {plan['version'] or '—'}\n"
            f"  [dim]a[/] tags     {', '.join(plan['tags']) or '[dim]none[/]'}"
        )
        lines = []
        for i, (v, subscribed, path, built, size) in enumerate(info["outputs"], 1):
            mark = "[green]✓[/]" if subscribed else "[dim]·[/]"
            lines.append(f"  [dim]{i}[/] {mark} {v:<14} {path.name:<40} {built:<10} {size}")
        self.query_one("#variants", Static).update("\n".join(lines))
        lines = []
        for name, desc, ok in info["parts"]:
            lines.append(f"  [red]{name:<32}[/] [dim]{desc}[/]" if not ok else f"  {name:<32} [dim]{desc}[/]")
        self.query_one("#parts", Static).update("\n".join(lines))

    def action_back(self):
        self.app.pop_screen()

    def action_cycle_status(self):
        self.app.cycle_status(self.catname, self.product)

    def action_bump(self, how):
        self.app.bump(self.catname, self.product, how)

    def action_tag(self):
        self.app.ask_tag(self.catname, self.product)

    def action_toggle_variant(self, index):
        info = product_info(self.app.project, self.catname, self.product)
        if index <= len(info["variants"]):
            self.app.toggle_variant(self.catname, self.product, info["variants"][index - 1])

    def action_build(self):
        self.app.build_product(self.catname, self.product)

    def action_open_output(self):
        self.app.open_output(self.catname, self.product)

    def action_check(self):
        self.app.action_check()

    def action_edit_catalog(self):
        self.app.open_in_editor(self.app.project.catalog_path(self.catname))


# ---------- app ----------


class Manager(App):
    TITLE = "imprenta"
    CSS = """
    DataTable { height: 1fr; }
    RichLog { height: 12; border-top: solid $accent; }
    #summary { height: 1; padding: 0 1; color: $text-muted; }
    .dim { color: $text-muted; }
    """
    BINDINGS = [
        Binding("enter", "open_product", "open product"),
        Binding("t", "row_cycle_status", "status"),
        Binding("v", "row_bump('minor')", "edition +.1"),
        Binding("V", "row_bump('major')", "edition +1"),
        Binding("a", "row_tag", "tag"),
        Binding("b", "row_build", "build"),
        Binding("B", "build_all", "build all"),
        Binding("o", "row_open_output", "open"),
        Binding("y", "edit_catalog", "edit catalog"),
        Binding("c", "check", "check"),
        Binding("g", "commit", "commit+push"),
        Binding("r", "refresh", "refresh"),
        Binding("q", "quit", "quit"),
    ]
    TABLE_ACTIONS = {
        "open_product",
        "row_cycle_status",
        "row_bump",
        "row_tag",
        "row_build",
        "row_open_output",
        "build_all",
        "edit_catalog",
        "check",
        "commit",
        "refresh",
    }

    def __init__(self, project: Project | None = None):
        super().__init__()
        self.project = project or Project.find()
        self.busy = None  # the title of the command running in the background, if any

    def on_mount(self):
        self.theme = "dracula"
        self.sub_title = self.project.root.name
        table = self.query_one(DataTable)
        table.add_columns(*COLUMNS)
        self.refresh_table()
        self.log_line(
            "[dim]Enter opens a product · t status · v/V edition · a tag · b build · B build all · "
            "o open · y edit catalog · c check · g commit+push[/]"
        )

    def check_action(self, action, parameters):
        """The table's keys belong to the table: hide them while a product screen is open."""
        if action in self.TABLE_ACTIONS and isinstance(self.screen, ProductScreen):
            return False
        return True

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="summary")
        yield DataTable(cursor_type="row", zebra_stripes=True)
        yield RichLog(highlight=True, markup=True, wrap=True)
        yield Footer()

    # ----- views -----

    def refresh_views(self):
        self.refresh_table()
        if isinstance(self.screen, ProductScreen):
            self.screen.refresh_view()

    def refresh_table(self):
        table = self.query_one(DataTable)
        cursor = table.cursor_row
        table.clear()
        for key, cells in rows(self.project):
            table.add_row(*cells, key=key)
        if table.row_count:
            table.move_cursor(row=min(cursor, table.row_count - 1))
        outputs = len(list(self.project.output.glob("*.*"))) if self.project.output.exists() else 0
        self.query_one("#summary", Static).update(
            f"{table.row_count} products · {outputs} output file(s) · {git_summary(self.project.root)}"
        )

    def current(self):
        """(catalog, product) of the highlighted row, or None."""
        table = self.query_one(DataTable)
        if not table.row_count:
            return None
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        catname, product = key.split("|")
        return catname, product

    def log_line(self, text):
        try:
            self.query_one(RichLog).write(text)
        except Exception:  # a product screen is on top: the log is behind it
            self.notify(ANSI.sub("", MARKUP.sub("", text))[:200], timeout=4)

    # ----- catalog edits -----

    def edit(self, catname, product, fn, what):
        """Apply `fn(doc, product)` to one catalog, save it, refresh, run the check."""
        doc = ce.load(self.project, catname)
        try:
            fn(doc, product)
        except ValueError as e:
            self.notify(str(e), severity="warning")
            return
        ce.save(self.project, catname, doc)
        self.log_line(f"catalog.{catname}: {what} → {product}")
        self.refresh_views()
        self.run_cmd([sys.executable, "-m", "imprenta", "check"], "check")

    def cycle_status(self, catname, product):
        def fn(doc, product):
            new = ce.next_status(ce.get_field(doc, product, "status"))
            ce.set_field(doc, product, "status", new)
            if new != "draft" and not ce.get_field(doc, product, "version"):
                ce.set_field(doc, product, "version", "0.1")

        self.edit(catname, product, fn, "status cycled")

    def bump(self, catname, product, how):
        def fn(doc, product):
            cur = ce.get_field(doc, product, "version")
            ce.set_field(doc, product, "version", ce.bump_version(cur, major=how == "major"))

        self.edit(catname, product, fn, f"edition bumped ({how})")

    def toggle_variant(self, catname, product, variant):
        known = list(self.project.catalog(catname).variants)
        self.edit(
            catname, product, lambda doc, p: ce.toggle_variant(doc, p, variant, known), f"variant {variant} toggled"
        )

    def ask_tag(self, catname, product):
        tags = self.project.catalog(catname).plan(product)["tags"]

        def go(tag):
            if tag:
                self.edit(catname, product, lambda doc, p: ce.toggle_tag(doc, p, tag), f"tag {tag} toggled")

        self.push_screen(
            TextScreen(
                f"Toggle a tag on {product}",
                [f"current: {', '.join(tags) or 'none'}"],
                "tag name (Enter to add/remove it, Esc to cancel)",
            ),
            go,
        )

    # ----- the same controls from the table row -----

    def with_row(self, fn, *args):
        row = self.current()
        if row:
            fn(*row, *args)

    def action_row_cycle_status(self):
        self.with_row(self.cycle_status)

    def action_row_bump(self, how):
        self.with_row(self.bump, how)

    def action_row_tag(self):
        self.with_row(self.ask_tag)

    def action_row_build(self):
        self.with_row(self.build_product)

    def action_row_open_output(self):
        self.with_row(self.open_output)

    def action_open_product(self):
        row = self.current()
        if row:
            self.push_screen(ProductScreen(*row))

    @on(DataTable.RowSelected)
    def row_selected(self, event):
        catname, product = event.row_key.value.split("|")
        self.push_screen(ProductScreen(catname, product))

    # ----- commands -----

    def run_cmd(self, argv, title, on_done=None):
        if self.busy:
            self.notify(f"still running: {self.busy}", severity="warning")
            return
        self.busy = title
        self.log_line(f"[bold]$ {' '.join(argv)}[/]")

        def worker():
            env = {**os.environ, "PYTHONUNBUFFERED": "1", "NO_COLOR": "1", "FORCE_COLOR": "0"}
            proc = subprocess.Popen(
                argv, cwd=self.project.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env
            )
            for line in proc.stdout:
                self.call_from_thread(self.log_line, ANSI.sub("", line.rstrip("\n")))
            code = proc.wait()
            self.call_from_thread(self.finished, title, code, on_done)

        self.run_worker(worker, thread=True, exclusive=False)

    def finished(self, title, code, on_done):
        self.busy = None
        self.log_line(f"[{'green' if code == 0 else 'red'}]{title}: {'ok' if code == 0 else f'exit {code}'}[/]")
        self.refresh_views()
        if on_done:
            on_done(code)

    def build_product(self, catname, product):
        spec = f"{catname}/{product}"
        self.run_cmd([sys.executable, "-m", "imprenta", "build", spec], f"build {spec}")

    def action_build_all(self):
        self.run_cmd([sys.executable, "-m", "imprenta", "build"], "build everything")

    def action_check(self):
        self.run_cmd([sys.executable, "-m", "imprenta", "check"], "check")

    def action_refresh(self):
        self.refresh_views()

    def open_output(self, catname, product):
        path, _ = newest_output(self.project, catname, product)
        if not path:
            self.notify("not built yet: press b", severity="warning")
            return
        subprocess.Popen([opener(), str(path)])
        self.log_line(f"opened {self.project.rel(path)}")

    def open_in_editor(self, path):
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        argv = [*editor.split(), str(path)] if editor else [opener(), str(path)]
        if editor and shutil.which(argv[0]) is None:
            self.notify(f"$EDITOR '{argv[0]}' not found", severity="error")
            return
        with self.suspend():
            subprocess.call(argv, cwd=self.project.root)
        self.log_line(f"edited {self.project.rel(path)}")
        self.refresh_views()
        self.run_cmd([sys.executable, "-m", "imprenta", "check"], "check")

    def action_edit_catalog(self):
        row = self.current()
        name = row[0] if row else self.project.catalog_names()[0]
        self.open_in_editor(self.project.catalog_path(name))

    def action_commit(self):
        status = subprocess.run(
            ["git", "status", "--short"], cwd=self.project.root, capture_output=True, text=True
        ).stdout.splitlines()
        if not status:
            self.notify("nothing to commit")
            return

        def go(message):
            if message:
                script = f"git add -A && git commit -q -m {sh_quote(message)} && git push -q && git log -1 --oneline"
                self.run_cmd(["bash", "-c", script], "commit+push")

        self.push_screen(
            TextScreen("Commit and push. Changes:", status, "commit message (Enter to commit, Esc to cancel)"), go
        )


def sh_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"
