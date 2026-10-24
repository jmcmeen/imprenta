"""`imprenta new`: the packaged starter is a valid project pinned to this engine."""

import pytest

from imprenta import Project
from imprenta.cli import main
from imprenta.new import pin_version, scaffold


def test_pin_version_is_the_public_release():
    assert pin_version("0.1.0") == "0.1.0"
    assert pin_version("0.2.3.dev4+gabc123") == "0.2.3"
    assert pin_version("1.0") == "1.0"


def test_scaffold_writes_a_project_that_passes_check(tmp_path):
    dest = scaffold(tmp_path / "almanac", version="9.9.9")
    assert (dest / ".gitignore").is_file()
    assert (dest / ".github" / "workflows" / "check.yml").is_file()
    assert not list(dest.glob("dot-*"))
    assert not list(dest.rglob("__pycache__"))
    pyproject = (dest / "pyproject.toml").read_text()
    assert 'name = "almanac"' in pyproject
    assert '"imprenta[tui]==9.9.9"' in pyproject
    assert "{{" not in pyproject
    for name in ("README.md", "CLAUDE.md", "package.json"):
        assert "{{" not in (dest / name).read_text()
    errors, warnings = Project(dest).check()
    assert errors == []
    assert warnings == []


def test_scaffold_refuses_a_non_empty_folder_or_a_file(tmp_path):
    (tmp_path / "taken").mkdir()
    (tmp_path / "taken" / "note.txt").write_text("x")
    with pytest.raises(FileExistsError):
        scaffold(tmp_path / "taken", version="1.0.0")
    (tmp_path / "file").write_text("x")
    with pytest.raises(FileExistsError):
        scaffold(tmp_path / "file", version="1.0.0")
    scaffold(tmp_path / "empty", version="1.0.0")  # a missing folder is created
    (tmp_path / "bare").mkdir()
    scaffold(tmp_path / "bare", version="1.0.0")  # an empty one is filled
    assert (tmp_path / "bare" / "catalog.main.yaml").is_file()
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".")]  # no work folder left behind


def test_scaffold_only_pins_a_release_number(tmp_path):
    for bad in ("1.0.0 @ https://evil.example/x.whl", "1.0.0; extra", "latest", "1"):
        with pytest.raises(ValueError):
            scaffold(tmp_path / "x", version=bad)
    assert not (tmp_path / "x").exists()


def test_scaffold_leaves_nothing_behind_on_failure(tmp_path, monkeypatch):
    import imprenta.new as new

    def boom(src, dst, subs):
        raise OSError("disk full")

    monkeypatch.setattr(new, "_copy", boom)
    with pytest.raises(OSError):
        scaffold(tmp_path / "almanac", version="1.0.0")
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(OSError):
        scaffold(tmp_path / "deep" / "er" / "almanac", version="1.0.0")
    assert list(tmp_path.iterdir()) == []  # the parents it made are gone too


def test_scaffold_fills_the_current_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    dest = scaffold(".", name="here", version="1.0.0")
    assert dest == tmp_path
    assert (tmp_path / "catalog.main.yaml").is_file()
    assert 'name = "here"' in (tmp_path / "pyproject.toml").read_text()
    assert not [
        p for p in tmp_path.iterdir() if p.name.startswith(".") and p.name != ".github" and p.name != ".gitignore"
    ]


def test_scaffold_refuses_symlinks(tmp_path):
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real")
    (tmp_path / "dangling").symlink_to(tmp_path / "nowhere")
    for name in ("link", "dangling"):
        with pytest.raises(FileExistsError):
            scaffold(tmp_path / name, version="1.0.0")
    assert list((tmp_path / "real").iterdir()) == []
    assert not (tmp_path / "nowhere").exists()


def test_scaffold_reports_a_destination_taken_during_the_copy(tmp_path, monkeypatch):
    import imprenta.new as new

    real_copy = new._copy

    def copy_then_race(src, dst, subs):
        real_copy(src, dst, subs)
        (tmp_path / "almanac").mkdir(exist_ok=True)
        (tmp_path / "almanac" / "theirs.txt").write_text("x")  # someone else got there first

    monkeypatch.setattr(new, "_copy", copy_then_race)
    with pytest.raises(FileExistsError):
        scaffold(tmp_path / "almanac", version="1.0.0")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["almanac"]  # theirs intact, our staging gone


def test_cli_new(tmp_path, capsys):
    assert main(["new", str(tmp_path / "series"), "--name", "my-series", "--pin", "1.2.3"]) == 0
    pyproject = (tmp_path / "series" / "pyproject.toml").read_text()
    assert 'name = "my-series"' in pyproject
    assert '"imprenta[tui]==1.2.3"' in pyproject
    assert "Wrote the starter project" in capsys.readouterr().out
