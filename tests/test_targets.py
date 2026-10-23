import copy

import pytest

from imprenta import Project, Target
from imprenta.catalog import Catalog
from imprenta.targets import SpecError, affected_targets, all_targets, parse_spec, spec_targets


def T(*specs, variants=("letter",)):
    return [Target(c, p, v) for c, p in specs for v in variants]


def test_all_targets_is_every_product_times_its_variants(project):
    cats = project.catalogs()
    assert all_targets(cats) == T(("main", "alpha"), ("main", "beta"), ("main", "anthology")) + T(
        ("other", "alpha"), variants=("letter", "ebook")
    )
    assert all_targets(cats, only=["ebook"]) == T(("other", "alpha"), variants=("ebook",))
    assert all_targets(cats, tag="release") == T(("main", "alpha"))
    assert project.targets(tag="nothing") == []


def test_affected_content_change_hits_every_target_whose_parts_include_it(project):
    cats = project.catalogs()
    assert affected_targets(["content/alpha.md"], cats) == T(("main", "alpha"), ("main", "anthology"))
    assert affected_targets(["content/intro.md"], cats) == T(("main", "alpha"), ("main", "beta"))
    assert affected_targets(["content/afterword.md"], cats) == T(("main", "anthology"))
    assert affected_targets(["content/alpha.es.md"], cats) == T(("other", "alpha"), variants=("letter", "ebook"))
    assert affected_targets(["content/shared/colophon.md", "content/nowhere.md", "README.md"], cats) == []


def test_affected_catalog_edit_hits_only_the_targets_whose_rendered_rows_changed(project):
    cats = project.catalogs()
    everything = all_targets(cats)

    def older(name, mutate):
        data = copy.deepcopy(cats[name].data)
        mutate(data)
        return {name: Catalog(project, name, data)}

    old = older("main", lambda d: d["products"]["beta"].__setitem__("version", "0.0"))
    assert affected_targets(["catalog.main.yaml"], cats, old_cats=old) == T(("main", "beta"))
    old = older("main", lambda d: d["recipes"]["leaflet"].__setitem__("parts", ["intro", "$name"]))
    assert affected_targets(["catalog.main.yaml"], cats, old_cats=old) == T(("main", "alpha"), ("main", "beta"))
    old = older("main", lambda d: d["products"]["anthology"]["parts"].__setitem__(1, {"toc": {"depth": 3}}))
    assert affected_targets(["catalog.main.yaml"], cats, old_cats=old) == T(("main", "anthology"))
    old = older("main", lambda d: d["groups"].__setitem__("all", ["beta", "alpha"]))
    assert affected_targets(["catalog.main.yaml"], cats, old_cats=old) == T(("main", "anthology"))
    old = older("main", lambda d: d["strings"].__setitem__("terms_title", "Words"))
    assert affected_targets(["catalog.main.yaml"], cats, old_cats=old) == T(
        ("main", "alpha"), ("main", "beta"), ("main", "anthology")
    )
    old = older(
        "main",
        lambda d: d["rendering"]["variants"].__setitem__(
            "letter", {"renderer": "pdf", "size": "a4", "palette": "color"}
        ),
    )
    assert affected_targets(["catalog.main.yaml"], cats, old_cats=old) == T(
        ("main", "alpha"), ("main", "beta"), ("main", "anthology")
    )
    # tags and subscriptions do not change any file
    old = older(
        "main",
        lambda d: (
            d["products"]["alpha"].__setitem__("tags", []),
            d["products"]["beta"].__setitem__("variants", ["letter", "mono"]),
        ),
    )
    assert affected_targets(["catalog.main.yaml"], cats, old_cats=old) == []
    # an unknown old catalog: that catalog rebuilds entirely, the other is untouched
    assert affected_targets(["catalog.other.yaml"], cats) == T(("other", "alpha"), variants=("letter", "ebook"))
    assert affected_targets(["catalog.main.yaml", "catalog.other.yaml"], cats) == everything


def test_affected_theme_files(project):
    cats = project.catalogs()
    everything = all_targets(cats)
    pdf = [t for t in everything if t.variant != "ebook"]
    assert affected_targets(["templates/palettes/mono.css"], cats) == []  # nobody subscribes mono
    assert affected_targets(["templates/sizes/letter.css"], cats) == pdf
    assert affected_targets(["templates/print.css"], cats) == pdf
    assert affected_targets(["templates/leaflet.html"], cats) == pdf
    assert affected_targets(["templates/epub.css"], cats) == [t for t in everything if t.variant == "ebook"]
    assert affected_targets(["templates/fonts/x.woff2"], cats) == everything
    assert affected_targets(["templates/print.css"], cats, tag="release") == T(("main", "alpha"))


def test_parse_spec_and_spec_targets(project):
    assert parse_spec(project, "main") == ("main", None, None)
    assert parse_spec(project, "alpha") == (None, "alpha", None)
    assert parse_spec(project, "other/alpha") == ("other", "alpha", None)
    assert parse_spec(project, "alpha.ebook") == (None, "alpha", "ebook")
    for bad in ("nowhere", "ghost/alpha", "other/beta"):
        with pytest.raises(SpecError):
            parse_spec(project, bad)
    assert spec_targets(project, "alpha") == [
        Target("main", "alpha", "letter"),
        Target("other", "alpha", "letter"),
        Target("other", "alpha", "ebook"),
    ]
    assert spec_targets(project, "main/alpha") == [Target("main", "alpha", "letter")]
    assert spec_targets(project, "beta.mono") == [Target("main", "beta", "mono")]  # subscribed or not
    assert spec_targets(project, "other") == T(("other", "alpha"), variants=("letter", "ebook"))
    with pytest.raises(KeyError):
        spec_targets(project, "beta.ghost")
    assert Target("main", "alpha", "letter").key == "main/alpha/letter"
    assert str(Target("main", "alpha", "letter")) == "main/alpha letter"
    assert isinstance(project, Project)
