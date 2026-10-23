import pytest

from imprenta import Project
from imprenta.catalog import Catalog, normalize_parts, substitute


def test_project_finds_the_catalogs_and_content(project, monkeypatch):
    assert project.catalog_names() == ["main", "other"]
    assert set(project.content_names()) >= {"alpha", "alpha.es", "shared/colophon", "intro"}
    assert project.content_path("shared/colophon") == project.content / "shared" / "colophon.md"
    nested = project.root / "content" / "shared"
    assert Project.find(nested).root == project.root
    with pytest.raises(FileNotFoundError):
        Project.find(project.root.parent)


def test_catalog_is_cached_on_mtime(project):
    a = project.catalog("main")
    assert project.catalog("main") is a
    path = project.catalog_path("main")
    path.write_text(path.read_text().replace("tags: [release]", "tags: [release, print]"))
    import os

    os.utime(path, None)
    b = project.catalog("main")
    assert b is not a and b.plan("alpha")["tags"] == ["release", "print"]


def test_product_def_merges_the_recipe_with_name_substituted(project):
    cat = project.catalog("main")
    spec = cat.product_def("alpha")
    assert spec["theme"] == "leaflet" and spec["status"] == "draft"
    assert spec["parts"] == [{"alpha-cover": {"style": "cover", "toc": False}}, "intro", "alpha", "terms", "back"]
    assert cat.product_def("anthology")["theme"] == "volume"
    assert cat.product_def("nowhere") is None
    assert substitute({"$name-x": ["$name"]}, "p") == {"p-x": ["p"]}
    assert normalize_parts(["a", {"b": {"style": "s"}}]) == [("a", {}), ("b", {"style": "s"})]


def test_plan_layers_defaults_under_the_product(project):
    main, other = project.catalog("main"), project.catalog("other")
    assert main.plan("alpha") == {"status": "draft", "version": "0.1", "variants": ["letter"], "tags": ["release"]}
    assert main.plan("anthology")["tags"] == [] and main.plan("anthology")["status"] is None
    assert other.plan("alpha")["variants"] == ["letter", "ebook"]
    assert Catalog(project, "x", {}).plan("p")["variants"] == []  # no rendering: nothing to subscribe


def test_rendering_accessors(project):
    cat = project.catalog("main")
    assert cat.default_variant == "letter" and cat.resolve_variant() == "letter"
    assert cat.variant_renderer("ebook") == "epub"
    assert [p.name for p in cat.variant_layers("mono")] == ["letter.css", "mono.css"]
    assert cat.variant_meta("letter")["size_css"] == "sizes/letter.css"
    assert cat.variant_filter(bundle="shop") == ["letter", "mono"] and cat.variant_filter() is None
    with pytest.raises(KeyError):
        cat.resolve_variant("ghost")
    with pytest.raises(KeyError):
        cat.variant_filter(bundle="ghost")


def test_resolve_parts_expands_groups_and_drops_missing_files(project):
    cat = project.catalog("main")
    assert cat.resolve_parts("alpha") == [
        ("alpha-cover", {"style": "cover", "toc": False}),
        ("intro", {}),
        ("alpha", {}),
        ("terms", {}),
    ]  # no back.md
    assert [n for n, _ in cat.resolve_parts("anthology")] == [
        "anthology-cover",
        "toc",
        "foreword",
        "alpha",
        "beta",
        "terms",
        "afterword",
    ]
    assert cat.content_names("anthology") == ["anthology-cover", "foreword", "alpha", "beta", "afterword"]
    other = project.catalog("other")
    assert [n for n, _ in other.resolve_parts("alpha")] == ["alpha.es", "terms"]  # intro.es is a placeholder
    assert cat.output_path("alpha", "ebook") == project.output / "alpha.main.ebook.epub"


def test_render_row_tracks_what_changes_the_file(project):
    cat = project.catalog("main")
    row = cat.render_row("alpha", "letter")
    assert row["theme"] == "leaflet" and row["product"] == {"status": "draft", "version": "0.1"}
    assert row["variant"] == {"renderer": "pdf", "size": "letter", "palette": "color"}
    assert "tags" not in row["product"] and "variants" not in row["product"]
    assert row["terms"]["term"] == ["term"]
    assert project.catalog("other").term_columns["term"] == ["término"]
