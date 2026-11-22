"""Окно вёрстки: загрузка файлов, кнопки панели, Ластик, отмена, сохранение PNG."""
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
    assert ts.win.lbl_status.text() == "Стрип очищен! Найдено баблов: 3, звуков/SFX: 0."


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
    size = first.block.size
    ts.win.btn_plus.click()
    ts.win.btn_wider.click()
    ts.win.btn_italic.click()
    ts.win.btn_str_plus.click()
    ts.win.btn_wt_plus.click()
    b = first.block
    assert (b.size, b.italic, b.stretch, b.bold) == (size + 0.5, True, 110, 1)
    assert block_state(second.block) == before_second
    assert ts.win.btn_undo.isEnabled()


def test_buttons_do_nothing_without_selection(loaded):
    ts = loaded
    before, history = ts.snapshot(), ts.doc.history_size
    ts.win.scene.clearSelection()
    ts.win.btn_plus.click()
    ts.win.btn_outline.click()
    assert ts.snapshot() == before
    assert ts.doc.history_size == history


def test_new_size_is_shown_on_canvas(loaded):
    ts = loaded
    item = ts.items[0]
    ts.select(item)
    before = item.text_rect().height()
    ts.win.adjust_font(4)
    assert item.text_rect().height() > before


def test_shadow_button_toggles_selected(loaded, tmp_path):
    txt = tmp_path / "t.txt"
    txt.write_text("- Привет!\nБАЦ!\n", encoding="utf-8")
    ts = loaded.load_txt(txt)
    reply, sound = ts.items
    ts.select(reply, sound)
    ts.win.btn_outline.click()
    assert (reply.block.bold, sound.block.shadow) == (2, False)


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
    ts.win.adjust_font(3)
    assert ts.win.shortcut_undo.key().toString() == "Ctrl+Z"
    ts.win.btn_undo.click()
    assert ts.snapshot() == before
    assert [it.isSelected() for it in ts.items] == [False, False, True, False]
    assert ts.win.lbl_status.text() == "Действие отменено!"


def test_eraser_and_undo(loaded):
    ts = loaded
    before = ts.doc.image.copy()
    ts.win.checkpoint()
    ts.win.erase_at(50, 450)
    assert (ts.doc.image != before).any()
    ts.win.undo_action()
    assert (ts.doc.image == before).all()


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
