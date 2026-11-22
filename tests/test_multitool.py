"""Подготовка к публикации (Multi tool): Нарезка, Квадрат, Acomics, Датировка, Лист проверки.

Эталоны сняты со старой версии на Wand/ImageMagick. После переезда на numpy
имена файлов, размеры и пиксели Нарезки и Квадрата совпадают точно, а у Acomics
масштабирование может отличаться на 1 уровень яркости в единичных пикселях —
это проверяет test_acomics_size (см. docs/adr/0001-drop-imagemagick.md).
"""
import shutil

import pytest

from conftest import fixture_path


def summary(golden_obj, results):
    return {name: {"shape": list(img.shape),
                   "pixels": golden_obj.image(name.rsplit(".", 1)[0].replace(" ", "_"), img)}
            for name, img in results.items()}


# ------------------------------------------------------------------ Нарезка

@pytest.mark.parametrize("page, contrast", [
    ("page_100.png", False),
    ("page_102.png", False),
    ("page_100.png", True),
    ("wpage_101.png", False),
], ids=["daily", "daily-sfx", "daily-contrast", "sunday"])
def test_slice_matches_golden(multitool, golden, page, contrast):
    mt = multitool.run(fixture_path("pages", page), "slice", contrast=contrast)
    assert mt.logs == []
    g = golden()
    g.check(summary(g, mt.results()))


def test_daily_page_gives_three_strips(multitool):
    mt = multitool.run(fixture_path("pages", "page_100.png"), "slice")
    assert sorted(mt.results()) == ["page_100 0.png", "page_100 1.png", "page_100 2.png"]


def test_sunday_page_gives_one_strip(multitool):
    mt = multitool.run(fixture_path("pages", "wpage_101.png"), "slice")
    assert sorted(mt.results()) == ["wpage_101.png"]


def test_slice_whole_folder(multitool, tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    shutil.copy(fixture_path("pages", "page_100.png"), src)
    shutil.copy(fixture_path("pages", "wpage_101.png"), src)
    (src / "notes.txt").write_text("не картинка")
    mt = multitool.run(src, "slice", folder=True)
    assert mt.logs == []
    assert sorted(mt.results()) == ["page_100 0.png", "page_100 1.png", "page_100 2.png", "wpage_101.png"]


# -------------------------------------------------------- Квадрат и Acomics

def test_square_matches_golden(multitool, golden):
    mt = multitool.run(fixture_path("strips", "pe1963-04-08.png"), "square")
    assert mt.logs == []
    g = golden()
    g.check(summary(g, mt.results()))


@pytest.mark.parametrize("strip, size", [
    ("pe1963-04-08.png", (223, 1024)),   # Ежедневный стрип
    ("pe1963-04-14.png", (705, 1024)),   # Воскресный стрип (высота оригинала >= 1000)
], ids=["daily", "sunday"])
def test_acomics_size(multitool, golden, strip, size):
    import cv2
    import numpy as np

    from conftest import GOLDEN_IMG

    mt = multitool.run(fixture_path("strips", strip), "acomics")
    (name, img), = mt.results().items()
    assert img.shape == size  # серый PNG ровно под Acomics
    golden().check({name: list(img.shape)})

    # Пиксели сверяем с картинкой, снятой со старой версии на ImageMagick:
    # допускается разница в 1 уровень яркости у единичных пикселей.
    ref_path = GOLDEN_IMG / f"wand__acomics__{strip}"
    if not ref_path.exists():
        pytest.skip("нет локального эталона ImageMagick")
    ref = cv2.imread(str(ref_path), cv2.IMREAD_UNCHANGED)
    diff = np.abs(ref.astype(int) - img.astype(int))
    assert diff.max() <= 1
    assert (diff > 0).mean() < 1e-4


def test_nothing_just_converts_to_png(multitool, tmp_path):
    src = tmp_path / "pe1963-04-08.png"
    shutil.copy(fixture_path("strips", "pe1963-04-08.png"), src)
    mt = multitool.run(src, "nothing")
    (name, img), = mt.results().items()
    assert name == "pe1963-04-08.png"
    assert img.shape[:2] == (488, 2229)


# ---------------------------------------------------------------- Датировка

def test_dating_assigns_consecutive_dates_across_new_year(multitool, tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    for i, d in enumerate((8, 9, 10)):
        shutil.copy(fixture_path("strips", f"pe1963-04-{d:02d}.png"), src / f"strip_{i}.png")
    mt = multitool.run(src, "date", folder=True, date="1963-12-30")
    assert mt.logs == []
    assert sorted(mt.results()) == ["pe1963-12-30.png", "pe1963-12-31.png", "pe1964-01-01.png"]


def test_dating_follows_alphabetical_file_order(multitool, tmp_path):
    """ХАРАКТЕРИЗАЦИЯ: порядок — по имени файла как строке, поэтому 10.png идёт раньше 2.png."""
    import cv2

    src = tmp_path / "in"
    src.mkdir()
    for name, width in (("1.png", 10), ("2.png", 20), ("10.png", 30)):
        cv2.imwrite(str(src / name), 255 * __import__("numpy").ones((5, width, 3), "uint8"))
    mt = multitool.run(src, "date", folder=True, date="1963-01-01")
    widths = {name: img.shape[1] for name, img in mt.results().items()}
    assert widths == {"pe1963-01-01.png": 10, "pe1963-01-02.png": 30, "pe1963-01-03.png": 20}


# ------------------------------------------------------------ Лист проверки

def test_validation_list_roundtrip(multitool, tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    for name in ("pe1963-04-08.png", "1963-04-09.png"):
        shutil.copy(fixture_path("strips", "pe1963-04-08.png"), src / name)
    multitool.run(src, "add_to_validation_list", folder=True)
    assert multitool.logs == [  # файлы обходятся по алфавиту: "1963-..." раньше "pe1963-..."
        "Стрип по дате: 1963-04-09 добавлен в лист",
        "Стрип по дате: 1963-04-08 добавлен в лист",
    ]
    listed = (tmp_path / "validation list.txt").read_text(encoding="utf-8")
    assert sorted(x.strip() for x in listed.split(",")) == ["1963-04-08", "1963-04-09"]

    multitool.logs.clear()
    check = tmp_path / "check"
    check.mkdir()
    for name in ("pe1963-04-08.png", "pe1963-04-10.png"):
        shutil.copy(fixture_path("strips", "pe1963-04-08.png"), check / name)
    multitool.run(check, "validate", folder=True)
    assert multitool.logs == [
        "Стрип по дате: 1963-04-08 уже переведен",
        "Стрип по дате: 1963-04-10 не переведен",
    ]


def test_validation_list_rejects_bad_names(multitool, tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    shutil.copy(fixture_path("strips", "pe1963-04-08.png"), src / "strip.png")
    multitool.run(src, "add_to_validation_list", folder=True)
    assert len(multitool.logs) == 1
    assert "не правильного формата" in multitool.logs[0]


def test_errors_go_to_log_not_exceptions(multitool, tmp_path):
    multitool.run(tmp_path / "нет такого файла.png", "slice")
    assert len(multitool.logs) == 1


# ------------------------------------------------------- вкладка в окне

def test_go_button_runs_selected_operation(ct, typesetter, multitool):
    tab = typesetter.win.tab_multitool
    tab.rb_file.setChecked(True)
    tab.edit_path.setText(str(fixture_path("strips", "pe1963-04-08.png")).replace("\\", "/"))
    next(rb for rb, op in tab.op_radios.items() if op == "square").setChecked(True)
    tab.btn_go.click()
    assert tab.output_box.toPlainText() == ""
    assert [img.shape for img in multitool.results().values()] == [(958, 1103)]


def test_acomics_and_validation_list_are_hidden_for_now(typesetter):
    shown = set(typesetter.win.tab_multitool.op_radios.values())
    assert shown == {"slice", "date", "square", "nothing"}
