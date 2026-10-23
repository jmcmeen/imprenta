import pytest

textual = pytest.importorskip("textual")

from imprenta import tui  # noqa: E402


def test_rows_and_product_info(project):
    rs = tui.rows(project)
    keys = [k for k, _ in rs]
    assert keys == ["main|alpha", "main|beta", "main|anthology", "other|alpha"]
    assert all(len(cells) == len(tui.COLUMNS) for _, cells in rs)
    alpha = dict(rs)["main|alpha"]
    assert alpha[0] == "alpha" and alpha[1] == "main" and alpha[4] == "release"
    info = tui.product_info(project, "main", "alpha")
    assert info["recipe"] == "leaflet" and info["theme"] == "leaflet"
    assert [n for n, _, ok in info["parts"]] == ["alpha-cover", "intro", "alpha", "terms", "back"]
    assert [ok for _, _, ok in info["parts"]] == [True, True, True, True, False]  # back.md is missing
    assert [(v, sub) for v, sub, *_ in info["outputs"]] == [("letter", True), ("mono", False), ("ebook", False)]


async def test_app_mounts_opens_a_product_and_edits_it(project):
    app = tui.Manager(project)
    async with app.run_test(size=(140, 40)) as pilot:
        assert app.theme == "dracula"
        table = app.query_one(tui.DataTable)
        assert table.row_count == 4
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, tui.ProductScreen)
        for key in ("enter", "B", "g", "r"):  # table-only keys are inert here
            await pilot.press(key)
            await pilot.pause(0.1)
        assert isinstance(app.screen, tui.ProductScreen)
        await pilot.press("2")  # subscribe mono
        await pilot.pause(0.3)
        for _ in range(40):
            if not app.busy:
                break
            await pilot.pause(0.25)
        assert project.catalog("main").plan("alpha")["variants"] == ["letter", "mono"]
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, tui.ProductScreen)
