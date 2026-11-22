"""Окно вёрстки: загрузка файлов, кнопки панели, Шрифты, Карандаш, отмена, сохранение PNG."""
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from conftest import block_state, fixture_path

DATA = Path(__file__).parent / "data"


# ----------------------------------------------------------------- эталоны

@pytest.mark.parametrize("strip, translation", [
    ("pe1963-04-08", DATA / "pe1963-04-08.txt"),
    ("pe1963-04-13", None),  # перевод вытащен из PSD команды
], ids=["pe1963-04-08", "pe1963-04-13"])
def test_typeset_matches_golden(typesetter, golden, tmp_path, monkeypatch, strip, translation):
    """Тот же результат, что давал монолит: тексты, места, кегли, очистка и итоговый PNG."""
    translation = translation or fixture_path("translations", f"{strip}.txt")
    ts = typesetter.load_image(fixture_path("strips", f"{strip}.png")).load_txt(translation)
    g = golden()
    rendered = ts.render(tmp_path / "out.png", monkeypatch)
    g.check({
        "status": ts.win.lbl_status.text(),
        "blocks": ts.snapshot(),
        "cleaned": g.image("cleaned", ts.doc.image),
        "rendered": g.image("rendered", rendered),
    })


# ---------------------------------------------------------------- загрузка

def test_status_after_image_only(typesetter):
    ts = typesetter.load_image(fixture_path("strips", "pe1963-04-08.png"))
    assert ts.items == []
    assert ts.win.lbl_status.text() == "Стрип очищен! Найдено баблов: 4, звуков: 0."


def test_translation_loaded_before_image_is_applied_when_image_arrives(typography, typesetter):
    from conftest import Typesetter

    ts = typesetter.load_txt(DATA / "pe1963-04-08.txt").load_image(fixture_path("strips", "pe1963-04-08.png"))
    reference = Typesetter(typography)
    reference.load_image(fixture_path("strips", "pe1963-04-08.png")).load_txt(DATA / "pe1963-04-08.txt")
    assert ts.snapshot() == reference.snapshot()
    assert ts.win.lbl_status.text() == reference.win.lbl_status.text()
    reference.win.close()


def test_unreadable_image_shows_error(typesetter, tmp_path, monkeypatch):
    from rus_peanuts.ui import main_window

    errors = []
    monkeypatch.setattr(main_window.QMessageBox, "critical", staticmethod(lambda *a, **k: errors.append(a)))
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    typesetter.load_image(bad)
    assert len(errors) == 1


# ------------------------------------------------------------ правка блоков

@pytest.fixture
def loaded(typesetter):
    return typesetter.load_image(fixture_path("strips", "pe1963-04-08.png")).load_txt(DATA / "pe1963-04-08.txt")


def test_toolbar_edits_only_selected_blocks(loaded):
    ts = loaded
    first, second = ts.items[0], ts.items[1]
    before_second = block_state(second.block)
    ts.select(first)
    ts.win.btn_italic.click()
    ts.win.spin_stretch.setValue(130)
    ts.win.spin_bold.setValue(3)
    b = first.block
    assert (b.italic, b.stretch, b.bold) == (True, 130, 3)
    assert block_state(second.block) == before_second
    assert ts.doc.history_size == 1 + 3  # загрузка перевода + три правки


def test_one_value_for_several_selected_blocks(loaded):
    ts = loaded
    ts.select(ts.items[0], ts.items[1])
    ts.win.spin_bold.setValue(4)
    assert [it.block.bold for it in ts.items] == [4, 4, 0, 0]


def test_controls_show_selected_block_and_are_off_without_selection(loaded):
    ts = loaded
    ts.items[1].block.set_bold(5)
    ts.items[1].block.set_stretch(150)
    ts.items[1].block.set_italic(True)
    ts.select(ts.items[1])
    win = ts.win
    assert (win.spin_bold.value(), win.spin_stretch.value(), win.btn_italic.isChecked()) == (5, 150, True)
    assert ts.doc.history_size == 1  # показ значений не считается правкой
    win.scene.clearSelection()
    assert not any(w.isEnabled() for w in (win.spin_bold, win.spin_stretch, win.btn_italic,
                                           win.combo_font, win.btn_arch))


def test_buttons_do_nothing_without_selection(loaded):
    ts = loaded
    before, history = ts.snapshot(), ts.doc.history_size
    ts.win.scene.clearSelection()
    ts.win.set_font("MPMangaFontBold")
    ts.win.set_bold(7)
    assert ts.snapshot() == before
    assert ts.doc.history_size == history


def test_new_style_is_shown_on_canvas(loaded):
    ts = loaded
    item = ts.items[0]
    ts.select(item)
    before = item.text_rect().height()
    ts.win.spin_stretch.setValue(200)
    assert item.text_rect().height() > before  # колонка той же ширины, строк стало больше


def test_toolbar_fits_full_hd_screen(typesetter):
    assert typesetter.win.minimumSizeHint().width() <= 1400


def test_strip_is_fitted_to_window_and_zoom_works(loaded):
    win = loaded.win
    win.resize(1320, 860)
    win.show()
    view = win.view
    view.fit()
    fitted = view.zoom_level
    assert fitted < 1.0  # стрип 2229 px шире окна — уменьшен
    vp = view.viewport().rect()
    shown = view.mapToScene(vp).boundingRect()
    assert shown.width() >= win.scene.sceneRect().width() - 1  # виден целиком по ширине
    view.zoom(2)
    assert not view.fit_mode and abs(view.zoom_level - 2 * fitted) < 1e-6
    view.fit()
    assert view.fit_mode and abs(view.zoom_level - fitted) < 1e-6
    win.hide()


# ---------------------------------------------------------------- Шрифты

def choose_font(win, postscript):
    """Как выбор в выпадающем списке шрифтов мышью."""
    index = win.combo_font.findData(postscript)
    assert index >= 0, postscript
    win.combo_font.setCurrentIndex(index)
    win.combo_font.activated.emit(index)


def test_font_list_shows_the_whole_font_set(loaded):
    combo = loaded.win.combo_font
    names = {combo.itemData(i): combo.itemText(i) for i in range(combo.count())}
    assert names["PeanutsRusbyme-Regular"] == "Peanuts by me"     # название — как у файла шрифта
    assert names["MPMangaFontBold"] == "Mp Manga Bold Shadow"
    assert "MPMangaFontBold-Bold" in names


def test_choosing_a_font_changes_selected_blocks_and_can_be_undone(loaded):
    ts = loaded
    first, second, third = ts.items[0], ts.items[1], ts.items[2]
    ts.select(first, second)
    history = ts.doc.history_size
    choose_font(ts.win, "MPMangaFontBold")
    assert [it.block.font for it in ts.items] == ["MPMangaFontBold"] * 2 + ["PeanutsRusbyme-Regular"] * 2
    assert ts.doc.history_size == history + 1
    family = ts.win.typography.fonts.get("MPMangaFontBold").family
    assert first.font().family() == family                       # видно на холсте
    ts.select(third)
    assert ts.win.combo_font.currentData() == "PeanutsRusbyme-Regular"
    ts.win.btn_undo.click()
    assert [it.block.font for it in ts.items] == ["PeanutsRusbyme-Regular"] * 4


def test_recent_font_goes_to_the_top_of_the_list(loaded):
    ts = loaded
    ts.select(ts.items[0])
    choose_font(ts.win, "MPMangaFontBold-Bold")
    assert ts.win.combo_font.itemData(0) == "MPMangaFontBold-Bold"
    assert ts.win.combo_font.currentData() == "MPMangaFontBold-Bold"


def test_block_with_missing_font_is_shown_and_kept(loaded):
    ts = loaded
    ts.items[0].block.set_font("TroubleSide")
    ts.select(ts.items[0])
    combo = ts.win.combo_font
    assert combo.currentIndex() == -1 and combo.placeholderText() == "нет шрифта: TroubleSide"
    assert ts.items[0].block.font == "TroubleSide"


def test_added_font_is_copied_and_listed(typography, tmp_path):
    from conftest import ROOT, Typesetter
    from rus_peanuts.typesetting.fonts import load_fonts
    from rus_peanuts.typesetting.layout import Typography

    empty = tmp_path / "fonts"
    ts = Typesetter(Typography(load_fonts(search_dirs=[], folder=str(empty))))
    assert ts.win.combo_font.count() == 0
    not_a_font = tmp_path / "readme.ttf"
    not_a_font.write_bytes(b"hello")
    added = ts.win.add_fonts([str(ROOT / "fonts" / "Mp Manga Bold Shadow.ttf"), str(not_a_font)])
    assert [f.postscript for f in added] == ["MPMangaFontBold"]
    assert sorted(p.name for p in empty.iterdir()) == ["Mp Manga Bold Shadow.ttf"]
    assert ts.win.combo_font.itemData(0) == "MPMangaFontBold"
    assert ts.win.lbl_status.text() == "Добавлено шрифтов: 1"
    ts.win.close()


def test_delete_key_removes_selected_blocks(loaded):
    ts = loaded
    victim = ts.items[0]
    ts.select(victim)
    QTest.keyClick(ts.win, Qt.Key.Key_Delete)
    assert victim not in ts.items
    assert victim.block not in ts.doc.blocks
    assert len(ts.doc.blocks) == 3


def test_moving_a_block_updates_document(loaded):
    item = loaded.items[0]
    item.setPos(item.pos().x() + 30, item.pos().y() + 5)
    assert (item.block.x, item.block.y) == (item.pos().x(), item.pos().y())


# ----------------------------------------------------------------- отмена

def test_undo_button_undoes_and_restores_selection(loaded):
    ts = loaded
    before = ts.snapshot()
    ts.select(ts.items[2])
    ts.win.spin_bold.setValue(2)
    assert ts.win.shortcut_undo.key().toString() == "Ctrl+Z"
    ts.win.btn_undo.click()
    assert ts.snapshot() == before
    assert [it.isSelected() for it in ts.items] == [False, False, True, False]
    assert ts.win.lbl_status.text() == "Действие отменено!"


# --------------------------------------------------------------- Карандаш

def drag(view, button, scene_points):
    """Штрих мышью по холсту через точки стрипа."""
    from PyQt6.QtCore import QEvent, QPointF
    from PyQt6.QtGui import QMouseEvent
    from PyQt6.QtWidgets import QApplication

    def send(kind, pt, buttons):
        pos = QPointF(view.mapFromScene(QPointF(*pt)))
        ev = QMouseEvent(kind, pos, view.viewport().mapToGlobal(pos), button, buttons,
                         Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(view.viewport(), ev)

    send(QEvent.Type.MouseButtonPress, scene_points[0], button)
    for pt in scene_points[1:]:
        send(QEvent.Type.MouseMove, pt, button)
    send(QEvent.Type.MouseButtonRelease, scene_points[-1], Qt.MouseButton.NoButton)


@pytest.fixture
def shown(loaded):
    loaded.win.resize(1320, 860)
    loaded.win.show()
    loaded.win.view.zoom(1 / loaded.win.view.zoom_level)  # 100 %: точка стрипа = точка экрана
    yield loaded
    loaded.win.hide()


def test_pencil_paints_black_stroke_and_one_undo_step(shown):
    ts, win = shown, shown.win
    win.btn_black.click()                       # выбор цвета включает Карандаш
    assert win.btn_pencil.isChecked() and win.view.pencil
    win.spin_brush.setValue(10)
    before, history = ts.doc.image.copy(), ts.doc.history_size
    win.view.centerOn(300, 440)
    drag(win.view, Qt.MouseButton.LeftButton, [(250, 440), (300, 440), (350, 440)])
    assert (ts.doc.image[436:445, 250:351] == 0).all()
    assert ts.doc.history_size == history + 1
    win.btn_undo.click()
    assert (ts.doc.image == before).all()


def test_pencil_does_not_move_blocks(shown):
    ts, win = shown, shown.win
    item = ts.items[0]
    win.btn_pencil.click()
    start = item.pos()
    center = item.sceneBoundingRect().center()
    win.view.centerOn(center)
    drag(win.view, Qt.MouseButton.LeftButton, [(center.x(), center.y()), (center.x() + 60, center.y() + 20)])
    assert item.pos() == start and not item.isSelected()


def test_right_button_erases_white_without_pencil(shown):
    ts, win = shown, shown.win
    assert not win.btn_pencil.isChecked()
    win.view.centerOn(300, 440)
    drag(win.view, Qt.MouseButton.RightButton, [(300, 440), (320, 440)])
    assert (ts.doc.image[440, 300:321] == 255).all()


def test_cursor_button_and_escape_turn_pencil_off(loaded):
    win = loaded.win
    assert win.btn_cursor.isChecked() and not win.btn_cursor.icon().isNull()
    win.btn_pencil.click()
    assert win.view.pencil and not win.btn_cursor.isChecked()
    win.btn_cursor.click()
    assert not win.btn_pencil.isChecked() and not win.view.pencil and win.view.isInteractive()
    win.btn_pencil.click()
    QTest.keyClick(win, Qt.Key.Key_Escape)
    assert win.btn_cursor.isChecked() and not win.view.pencil


def test_pencil_survives_loading_a_translation(shown, tmp_path):
    ts, win = shown, shown.win
    win.btn_black.click()
    win.spin_brush.setValue(10)
    win.view.centerOn(300, 440)
    drag(win.view, Qt.MouseButton.LeftButton, [(250, 440), (350, 440)])
    txt = tmp_path / "t.txt"
    txt.write_text("- Новая реплика\n", encoding="utf-8")
    ts.load_txt(txt)
    assert (ts.doc.image[436:445, 250:351] == 0).all()


def test_no_painting_while_original_is_shown(loaded):
    win = loaded.win
    win.btn_orig.click()
    assert not win.can_paint
    win.btn_orig.click()
    assert win.can_paint


def test_new_image_keeps_translation_and_clears_history(loaded):
    ts = loaded
    ts.win.checkpoint()
    ts.load_image(fixture_path("strips", "pe1963-04-09.png"))
    assert not ts.doc.can_undo and not ts.win.btn_undo.isEnabled()
    assert len(ts.items) == 4


# --------------------------------------------------------- показ оригинала

def test_show_original_hides_blocks_and_back(loaded):
    ts = loaded
    ts.win.toggle_original(True)
    assert not any(it.isVisible() for it in ts.items)
    assert ts.win.btn_orig.text() == "Вернуть результат"
    ts.win.toggle_original(False)
    assert all(it.isVisible() for it in ts.items)
