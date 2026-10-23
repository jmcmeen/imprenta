import time

from imprenta import content, parts
from imprenta.build import inputs, is_fresh, row_stamp, write_stamp
from imprenta.targets import Target


def test_content_helpers(project):
    path = project.content_path("alpha")
    assert content.read_meta(path) == {"label": "Alpha"}
    assert content.read_text(path).startswith("# All about alpha")
    assert content.first_heading(content.read_text(path)) == "All about alpha"
    assert content.word_count(path) == len(content.strip_comments(content.read_text(path)).split())
    assert content.is_placeholder(project.content_path("intro.es"))
    assert not content.is_placeholder(path)
    assert content.css_name("shared/intro.en") == "shared-intro-en"
    assert content.default_label("shared/intro.en") == "Intro"
    assert project.content_label("alpha") == "Alpha" and project.content_label("intro") == "Intro"


def test_parse_tables_follows_the_column_aliases():
    text = "| Término | Significado | Ejemplo |\n| --- | --- | --- |\n| **Tío** | Colega | *Oye* |\n"
    assert list(parts.parse_tables(text, {"term": ["term"], "literal": [], "meaning": ["meaning"], "example": []})) == [
        ("Tío", "", "", "")
    ]  # no alias matched: term only
    cols = {"term": ["término"], "literal": [], "meaning": ["significado"], "example": ["ejemplo"]}
    assert list(parts.parse_tables(text, cols)) == [("Tío", "", "Colega", "Oye")]


def test_terms_markdown_builds_an_alphabetical_glossary(project):
    cat = project.catalog("main")
    single = parts.terms_markdown(cat, ["alpha-cover", "intro", "alpha"]).splitlines()
    assert single[0] == "# Glossary" and single[2] == "| Term | Literal | Meaning | Example |"
    assert [line.split("|")[1].strip() for line in single[4:]] == ["Guay", "Tío"]  # molar and Secret left out
    many = parts.terms_markdown(cat, ["foreword", "alpha", "beta"], {"title": "All terms"}).splitlines()
    assert many[0] == "# All terms" and many[2] == "| Term | Source | Meaning | Example |"
    assert [line.split("|")[1:3] for line in many[4:]] == [
        [" Guay ", " Alpha "],
        [" Guay ", " Beta "],
        [" Pata ", " Beta "],
        [" Tío ", " Alpha "],
    ]  # collisions adjacent
    other = project.catalog("other")
    es = parts.terms_markdown(other, ["alpha.es"]).splitlines()
    assert es[0] == "# Glosario" and [line.split("|")[1].strip() for line in es[4:]] == ["Tío"]


def test_toc_marker_and_wrapping(project):
    cat = project.catalog("main")
    assert parts.toc_markdown(cat) == '::: {.toc-marker depth="2" pages="true" title="Contents"}\n:::\n'
    assert parts.toc_markdown(cat, {"depth": 3, "pages": False, "title": "In this volume"}) == (
        '::: {.toc-marker depth="3" pages="false" title="In this volume"}\n:::\n'
    )
    assert (
        parts.part_classes("alpha-cover", {"style": "cover", "toc": False})
        == ".part .part-alpha-cover .style-cover .unlisted"
    )
    assert parts.wrap("# Hi\n", "shared/intro.en", {}) == ":::::: {.part .part-shared-intro-en}\n# Hi\n\n::::::\n"


def test_assemble_writes_one_wrapped_file_per_part(project):
    cat = project.catalog("main")
    files, names = parts.assemble(cat, "alpha", project.tmp)
    assert [f.name for f in files] == [
        "alpha.main.00.alpha-cover.md",
        "alpha.main.01.intro.md",
        "alpha.main.02.alpha.md",
        "alpha.main.03.terms.md",
    ]
    assert names == ["alpha-cover", "intro", "alpha"]
    assert files[0].read_text().startswith(":::::: {.part .part-alpha-cover .style-cover .unlisted}\nThe eyebrow")
    assert "label:" not in files[2].read_text()  # front matter stripped
    files, _ = parts.assemble(cat, "anthology", project.tmp)
    assert files[1].read_text().splitlines()[1].startswith("::: {.toc-marker")
    assert parts.page_title(cat, "alpha") == "Alpha Cover"
    assert parts.page_lang(cat, "alpha") is None
    assert parts.page_lang(project.catalog("other"), "alpha") == "es"


def test_freshness_uses_inputs_and_the_stamp(project):
    t = Target("main", "alpha", "letter")
    files = inputs(project, t)
    assert project.content_path("alpha") in files and project.templates / "print.css" in files
    out = project.output / "alpha.main.letter.pdf"
    out.parent.mkdir()
    stamp = row_stamp(project, t)
    assert "imprenta" in stamp
    time.sleep(0.01)
    out.write_text("pdf")
    assert not is_fresh(out, files, stamp, project.tmp)  # never stamped
    write_stamp(out, stamp, project.tmp)
    assert is_fresh(out, files, stamp, project.tmp)
    assert not is_fresh(out, files, stamp + "x", project.tmp)  # the rows changed
    time.sleep(0.01)
    project.content_path("alpha").write_text("# Alpha\n\nnew\n")
    assert not is_fresh(out, files, stamp, project.tmp)  # a file changed
