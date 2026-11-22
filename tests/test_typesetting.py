"""Вёрстка: расстановка Перевода по найденным местам, ручная правка, отмена, сохранение."""
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QGraphicsTextItem

from conftest import fixture_path

DATA = Path(__file__).parent / "data"
FALLBACK_Y = 45  # запасной ряд мест вверху стрипа: x = 80 + i * 180, y = 45, 160 x 70


def center(block):
    r = QGraphicsTextItem.boundingRect(block)
    return block.pos().x() + r.center().x(), block.pos().y() + r.center().y()


def inside(point, box, slack=2):
    x, y = point
    bx, by, bw, bh = box[:4]
    return bx - slack <= x <= bx + bw + slack and by - slack <= y <= by + bh + slack


# ----------------------------------------------------------------- эталоны

@pytest.mark.parametrize("strip, translation", [
    ("pe1963-04-08", DATA / "pe1963-04-08.txt"),
    ("pe1963-04-13", None),  # перевод вытащен из PSD команды
], ids=["pe1963-04-08", "pe1963-04-13"])
def test_typeset_matches_golden(typesetter, golden, tmp_path, monkeypatch, strip, translation):
    translation = translation or fixture_path("translations", f"{strip}.txt")
    ts = typesetter.load_image(fixture_path("strips", f"{strip}.png")).load_txt(translation)
    g = golden()
    rendered = ts.render(tmp_path / "out.png", monkeypatch)
    g.check({
        "status": ts.win.lbl_status.text(),
        "blocks": ts.snapshot(),
        "cleaned": g.image("cleaned", ts.cleaned_image()),
        "rendered": g.image("rendered", rendered),
    })


# --------------------------------------------- сопоставление по порядку чтения

def test_replies_fill_bubbles_in_reading_order(typesetter):
    ts = typesetter.load_image(fixture_path("strips", "pe1963-04-08.png")).load_txt(DATA / "pe1963-04-08.txt")
    replies = [b for b in ts.blocks if b.is_bubble]
    for block, box in zip(replies, ts.bubbles):
        assert inside(center(block), box)


def test_extra_reply_goes_to_fallback_row(typesetter):
    """В 04-08 найдено 3 Бабла, а Реплик 4: четвёртая встаёт в запасной ряд вверху слева."""
    ts = typesetter.load_image(fixture_path("strips", "pe1963-04-08.png")).load_txt(DATA / "pe1963-04-08.txt")
    assert len(ts.bubbles) == 3
    fourth = [b for b in ts.blocks if b.is_bubble][3]
    assert inside(center(fourth), (80, FALLBACK_Y, 160, 70))


def test_extra_reply_steals_a_sound_slot(typesetter):
    """ХАРАКТЕРИЗАЦИЯ (вопрос 4, вероятно баг): лишняя Реплика сдвигает счётчик Звуков.
    В 04-12 найдено 4 Бабла и 2 Звука; в Переводе 5 Реплик и 2 Звука.
    Пятая Реплика занимает запасное место и «съедает» первый Звук:
    первый Звук встаёт на второе найденное место, второй — в запасной ряд,
    а первое найденное место Звука остаётся пустым."""
    ts = typesetter.load_image(fixture_path("strips", "pe1963-04-12.png")).load_txt(DATA / "pe1963-04-12_overflow.txt")
    assert (len(ts.bubbles), len(ts.sounds)) == (4, 2)
    sounds = [b for b in ts.blocks if not b.is_bubble]
    assert inside(center(sounds[0]), ts.sounds[1])
    assert inside(center(sounds[1]), (80 + 2 * 180, FALLBACK_Y, 160, 70))
    assert not any(inside(center(s), ts.sounds[0]) for s in sounds)


def test_sound_inherits_detected_arch(typesetter, tmp_path):
    ts = typesetter.load_image(fixture_path("strips", "pe1963-04-10.png"))
    txt = tmp_path / "t.txt"
    txt.write_text("БАЦ!\n", encoding="utf-8")
    ts.load_txt(txt)
    assert ts.sounds[0][4] != 0
    assert ts.snapshot()[0]["arch"] == ts.sounds[0][4]


def test_translation_loaded_before_image_is_applied_when_image_arrives(ct, typesetter):
    ts = typesetter.load_txt(DATA / "pe1963-04-08.txt").load_image(fixture_path("strips", "pe1963-04-08.png"))

    reference = type(typesetter)(ct)
    reference.load_image(fixture_path("strips", "pe1963-04-08.png")).load_txt(DATA / "pe1963-04-08.txt")
    assert ts.snapshot() == reference.snapshot()
    reference.win.close()


def test_image_without_translation_is_cleaned_with_no_blocks(typesetter):
    ts = typesetter.load_image(fixture_path("strips", "pe1963-04-08.png"))
    assert ts.blocks == []
    assert ts.win.lbl_status.text() == "Стрип очищен! Найдено баблов: 3, звуков/SFX: 0."


# --------------------------------------------------------- ручная правка

@pytest.fixture
def loaded(typesetter):
    return typesetter.load_image(fixture_path("strips", "pe1963-04-08.png")).load_txt(DATA / "pe1963-04-08.txt")


def test_shadow_button_means_different_things_for_reply_and_sound(loaded, tmp_path):
    """ХАРАКТЕРИЗАЦИЯ (вопрос про «Shadow / Обычный»): у Реплики кнопка переключает
    Жирность 0 <-> 2, у Звука — начертание Shadow <-> сплошное."""
    txt = tmp_path / "t.txt"
    txt.write_text("- Привет!\nБАЦ!\n", encoding="utf-8")
    ts = loaded.load_txt(txt)
    reply, sound = ts.blocks

    ts.select(reply, sound)
    ts.win.toggle_selected_outline()
    r, s = ts.snapshot()
    assert (r["bold"], r["is_outlined"]) == (2, False)
    assert (s["bold"], s["is_outlined"]) == (0, False)

    ts.win.toggle_selected_outline()
    r, s = ts.snapshot()
    assert (r["bold"], r["is_outlined"]) == (0, False)
    assert (s["bold"], s["is_outlined"]) == (0, True)


def test_toolbar_adjustments_and_limits(loaded):
    ts = loaded
    reply = ts.blocks[0]
    ts.select(reply)
    before = ts.block_state(reply)

    ts.win.adjust_font(0.5)
    ts.win.adjust_width(10)
    ts.win.toggle_italic()
    ts.win.adjust_stretch(10)
    ts.win.adjust_weight(1)
    after = ts.block_state(reply)
    assert after["size"] == before["size"] + 0.5
    assert after["width"] == round(before["width"] + 10, 2)
    assert (after["italic"], after["stretch"], after["bold"]) == (True, 110, 1)

    for _ in range(100):
        ts.win.adjust_font(-0.5)
        ts.win.adjust_stretch(-10)
        ts.win.adjust_weight(-1)
    low = ts.block_state(reply)
    assert (low["size"], low["stretch"], low["bold"]) == (5.0, 50, 0)

    for _ in range(100):
        ts.win.adjust_stretch(10)
        ts.win.adjust_weight(1)
    high = ts.block_state(reply)
    assert (high["stretch"], high["bold"]) == (400, 10)


def test_width_change_ignores_sounds(loaded, tmp_path):
    txt = tmp_path / "t.txt"
    txt.write_text("БАЦ!\n", encoding="utf-8")
    ts = loaded.load_txt(txt)
    sound = ts.blocks[0]
    ts.select(sound)
    before = ts.block_state(sound)["width"]
    ts.win.adjust_width(10)
    assert ts.block_state(sound)["width"] == before


def test_arch_is_clamped(loaded):
    block = loaded.blocks[0]
    block.set_arch(1000)
    assert block.arch_amount == 150
    block.set_arch(-1000)
    assert block.arch_amount == -150


def test_delete_key_removes_selected_blocks(loaded):
    ts = loaded
    n = len(ts.blocks)
    ts.select(ts.blocks[0])
    QTest.keyClick(ts.win, Qt.Key.Key_Delete)
    assert len(ts.blocks) == n - 1


# ----------------------------------------------------------------- отмена

def test_undo_restores_block_state(loaded):
    ts = loaded
    original = ts.snapshot()
    ts.select(ts.blocks[0])
    ts.win.adjust_font(2)
    ts.win.toggle_italic()
    assert ts.snapshot() != original

    ts.win.undo_action()
    ts.win.undo_action()
    assert ts.snapshot() == original


def test_undo_restores_erased_pixels(loaded):
    ts = loaded
    before = ts.cleaned_image().copy()
    ts.win.push_undo_state()            # так делает правая кнопка мыши перед ластиком
    ts.win.paint_white_spot(50, 450)
    assert (ts.cleaned_image() != before).any()
    ts.win.undo_action()
    assert (ts.cleaned_image() == before).all()


def test_undo_stack_keeps_last_40_states(loaded):
    ts = loaded
    for _ in range(60):
        ts.win.push_undo_state()
    assert len(ts.win.undo_stack) == 40


def test_loading_new_image_clears_undo(loaded):
    ts = loaded
    ts.win.push_undo_state()
    ts.load_image(fixture_path("strips", "pe1963-04-09.png"))
    # load_image сбрасывает стек, но затем заново применяет Перевод и кладёт одно состояние
    assert len(ts.win.undo_stack) == 1


# -------------------------------------------------------- показ оригинала

def test_show_original_hides_blocks_and_back(loaded):
    ts = loaded
    ts.win.toggle_original(True)
    assert not any(b.isVisible() for b in ts.blocks)
    assert ts.win.btn_orig.text() == "Вернуть результат"
    ts.win.toggle_original(False)
    assert all(b.isVisible() for b in ts.blocks)
