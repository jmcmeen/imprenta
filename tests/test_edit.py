import pytest

from imprenta import edit as ce

SAMPLE = """\
# the one yaml
defaults:
  variants: [letter]
  tags: [release]

recipes:
  leaflet: {theme: leaflet, parts: [$name-cover, $name]}
products:
  # the first batch
  alpha: {recipe: leaflet, status: draft, version: "0.1"}   # keep me
  volume:
    theme: volume
    version: "0.1"
    parts: [volume-cover, alpha]
"""


def test_round_trip_keeps_comments_quotes_and_order():
    assert ce.dumps(ce.loads(SAMPLE)) == SAMPLE


def test_set_field_edits_in_place_and_preserves_everything_else():
    doc = ce.loads(SAMPLE)
    ce.set_field(doc, "alpha", "status", "ready")
    ce.set_field(doc, "alpha", "version", "1.0")
    ce.set_field(doc, "volume", "version", "0.2")
    out = ce.dumps(doc)
    assert "# the first batch" in out and "# keep me" in out
    assert 'alpha: {recipe: leaflet, status: ready, version: "1.0"}' in out
    assert '    version: "0.2"\n' in out
    ce.set_field(doc, "alpha", "status", None)
    assert "status" not in ce.product_block(doc, "alpha")


def test_get_field_falls_back_to_defaults_for_variants_and_tags():
    doc = ce.loads(SAMPLE)
    assert list(ce.get_field(doc, "alpha", "variants")) == ["letter"]
    assert list(ce.get_field(doc, "alpha", "tags")) == ["release"]
    assert ce.get_field(doc, "alpha", "status") == "draft"
    assert ce.get_field(doc, "volume", "status") is None


def test_next_status_and_bump_version():
    assert [ce.next_status(s) for s in ("draft", "ready", "published", None)] == [
        "ready",
        "published",
        "draft",
        "draft",
    ]
    assert ce.bump_version("0.1") == "0.2"
    assert ce.bump_version("1.9") == "1.10"
    assert ce.bump_version("0.3", major=True) == "1.0"
    assert ce.bump_version(None) == "0.1"
    assert ce.bump_version("beta") == "beta"


def test_toggle_variant_keeps_flow_style_and_drops_the_field_at_defaults():
    doc = ce.loads(SAMPLE)
    known = ["letter", "mono", "ebook"]
    assert ce.toggle_variant(doc, "alpha", "ebook", known) == ["letter", "ebook"]
    assert 'alpha: {recipe: leaflet, status: draft, version: "0.1", variants: [letter, ebook]}' in ce.dumps(doc)
    assert ce.toggle_variant(doc, "alpha", "ebook", known) == ["letter"]
    assert "variants" not in ce.product_block(doc, "alpha")  # back at defaults: field dropped
    with pytest.raises(ValueError):
        ce.toggle_variant(doc, "alpha", "letter", known)  # never remove the last one


def test_toggle_tag():
    doc = ce.loads(SAMPLE)
    assert ce.toggle_tag(doc, "alpha", "release") == []  # inherited from defaults, now off
    assert "tags: []" in ce.dumps(doc)
    assert ce.toggle_tag(doc, "alpha", "release") == ["release"]
    assert "tags" not in ce.product_block(doc, "alpha")  # equal to defaults again: dropped
    assert ce.toggle_tag(doc, "volume", "print") == ["release", "print"]
    assert "tags: [release, print]" in ce.dumps(doc)


def test_load_and_save_through_the_project(project):
    doc = ce.load(project, "main")
    ce.set_field(doc, "beta", "status", "ready")
    ce.save(project, "main", doc)
    assert project.catalog("main").plan("beta")["status"] == "ready"
    assert "# $name is the product" not in project.catalog_path("main").read_text()  # nothing invented
