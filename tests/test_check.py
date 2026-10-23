from conftest import MAIN, VARIANTS, write_project

from imprenta.check import run


def errors_of(project):
    errors, _ = run(project)
    return errors


def test_sample_project_passes_except_for_its_known_gaps(project):
    errors, warnings = run(project)
    assert errors == [
        str(project.catalog_path("main"))
        + ": recipes.leaflet.parts names 'back' but it is not toc, terms, a group or a content file",
        str(project.catalog_path("main"))
        + ": products.alpha.parts names 'back' but it is not toc, terms, a group or a content file",
        str(project.catalog_path("main"))
        + ": products.beta.parts names 'back' but it is not toc, terms, a group or a content file",
    ]
    assert warnings == ["content/shared/colophon.md: no product in any catalog uses it"]


def fixed(project):
    """The sample with its gaps closed: back.md exists, the colophon is used."""
    (project.content / "back.md").write_text("# Back\n\nEnd.\n")
    path = project.catalog_path("main")
    path.write_text(path.read_text().replace("      - afterword\n", "      - afterword\n      - shared/colophon\n"))
    return project


def test_fixed_project_is_clean(project):
    assert run(fixed(project)) == ([], [])


def test_content_rules(project):
    fixed(project)
    (project.content / "foreword.md").write_text("Intro.\n\n# Title\n\n##### Deep\n\n# Again\n")
    errors = errors_of(project)
    assert any("foreword.md:1: content must start with its H1 title" in e for e in errors)
    assert any("deeper than H4" in e for e in errors)
    assert any("second H1" in e for e in errors)
    (project.content / "alpha-cover.md").write_text("Eyebrow\n\nNo title.\n")  # styled: may open with a paragraph
    (project.content / "foreword.md").write_text("---\n- list\n---\n# Foreword\n")
    errors = errors_of(project)
    assert any("alpha-cover.md: no H1 title" in e for e in errors)
    assert any("front matter must be a mapping" in e for e in errors)
    (project.content / "README.txt").write_text("x")
    (project.content / ".obsidian").mkdir()
    (project.content / ".obsidian" / "workspace.json").write_text("{}")
    errors, warnings = run(project)
    assert any("README.txt: not a content file" in e for e in errors)
    assert not any(".obsidian" in e for e in errors + warnings)


def test_catalog_section_rules(project):
    fixed(project)
    path = project.catalog_path("main")
    path.write_text(path.read_text() + "lang: en\nsync: true\nextra: {}\n")
    errors = errors_of(project)
    assert any("'lang' is not a catalog section" in e and "no language concept" in e for e in errors)
    assert any("'sync' is not a catalog section" in e and "tag instead" in e for e in errors)
    assert any("'extra' is not a catalog section" in e for e in errors)


def test_products_parts_settings_and_recipes_are_checked(project):
    fixed(project)
    path = project.catalog_path("main")
    path.write_text(
        MAIN.replace(
            "recipes:\n  leaflet:\n    theme: leaflet\n",
            "recipes:\n  bad: {color: red}\n  leaflet:\n    theme: nope\n",
        )
        .replace(
            "products:\n",
            "products:\n"
            "  other: {recipe: missing, parts: [$name], sync: true, price: 5}\n"
            "  'dotted.name': {theme: leaflet, parts: [intro]}\n",
        )
        .replace(
            "      - toc: {depth: 2}\n",
            "      - toc: {depth: two, color: red}\n      - foreword: {size: big}\n"
            "      - terms: {title: 1}\n      - ghost\n",
        )
    )
    errors = errors_of(project)
    for needle in (
        "recipes.leaflet.theme 'nope' has no templates/nope.html",
        "recipes.bad.color is not a recipe field",
        "products.other.recipe 'missing' is not a recipe",
        "products.other.parts: '$name' only makes sense inside a recipe",
        "products.other.sync is not a field",
        "products.other.price is not a product field",
        "products.dotted.name: a product name may not contain '.' or '/'",
        "toc.depth must be int",
        "'toc' has no setting 'color'",
        "'foreword' has no setting 'size'",
        "terms.title must be str",
        "products.anthology.parts names 'ghost' but it is not toc, terms, a group or a content file",
    ):
        assert any(needle in e for e in errors), needle


def test_groups_terms_and_publishing_fields(project):
    fixed(project)
    path = project.catalog_path("main")
    path.write_text(
        MAIN.replace(
            "groups:\n  all: [alpha, beta]\n  first: [alpha]\n",
            "groups:\n  all: [alpha, cuba]\n  foreword: [alpha]\n  terms: [alpha]\n  empty: []\n",
        )
        .replace(
            '  alpha: {recipe: leaflet, status: draft, version: "0.1", tags: [release]}\n',
            "  alpha: {recipe: leaflet, status: wip, version: 0.1, tags: release, variants: [ghost]}\n",
        )
        .replace(
            '  beta:  {recipe: leaflet, status: draft, version: "0.1"}\n',
            "  beta:  {recipe: leaflet, status: ready, variants: []}\n",
        )
        + "terms:\n  columns:\n    color: [x]\n    term: nope\n"
    )
    errors = errors_of(project)
    for needle in (
        "groups.all lists 'cuba', which is not a content file",
        "groups.foreword shares its name with a generated part, a content file or a product",
        "groups.terms shares its name",
        "groups.empty must be a non-empty list",
        "products.alpha.status must be one of",
        "products.alpha.version must be a quoted string",
        "products.alpha.tags must be a list of strings",
        "products.alpha.variants lists unknown variant 'ghost'",
        "products.beta.version is required once status is ready",
        "products.beta.variants must be a non-empty list",
        "terms.columns.color must be one of term, literal, meaning, example",
        "terms.columns.term must be one of term, literal, meaning, example mapped to a list",
    ):
        assert any(needle in e for e in errors), needle


def test_rendering_rules(project):
    fixed(project)
    path = project.catalog_path("main")
    path.write_text(
        MAIN.replace(
            VARIANTS,
            (
                "rendering:\n  default: nope\n  color: x\n  variants:\n"
                "    a4: {size: a4, palette: color}\n"
                "    nopal: {size: letter}\n"
                "    weird: {renderer: docx}\n"
                "    sized: {renderer: epub, size: letter}\n"
                "  bundles:\n    shop: [a4, ghost]\n"
            ),
        )
    )
    errors = errors_of(project)
    for needle in (
        "rendering.default must name one of the variants",
        "rendering.color is not a rendering field",
        "variants.a4.size 'a4' has no templates/sizes/a4.css",
        "variants.nopal.palette is missing",
        "renderer must be pdf or epub",
        "'size' does not apply to an epub variant",
        "bundles.shop lists unknown variant 'ghost'",
        "defaults.variants lists unknown variant 'letter'",
    ):
        assert any(needle in e for e in errors), needle
    path.write_text(MAIN.replace(VARIANTS, ""))
    assert any("rendering is missing" in e for e in errors_of(project))


def test_no_catalog_is_an_error(tmp_path):
    project = write_project(tmp_path)
    for p in tmp_path.glob("catalog.*.yaml"):
        p.unlink()
    assert run(project)[0] == [str(tmp_path / "catalog.<name>.yaml") + ": no catalog found"]
