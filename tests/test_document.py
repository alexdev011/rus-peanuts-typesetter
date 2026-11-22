"""Документ вёрстки: расстановка Перевода по местам, правки Текстовых блоков, отмена."""
from pathlib import Path

import pytest

from conftest import block_state, fixture_path
from rus_peanuts.typesetting import analysis, translation
from rus_peanuts.typesetting.document import FALLBACK_Y, Document, TextBlock

DATA = Path(__file__).parent / "data"
SHY = "\u00ad"


def strip(name):
    return analysis.load_image(fixture_path("strips", f"{name}.png"))


def lines(text):
    return translation.parse(text)


def center(doc, block):
    r = doc.typography.bounds(block)
    return block.x + r.center().x(), block.y + r.center().y()


def inside(point, box, slack=2):
    x, y = point
    bx, by, bw, bh = box[:4]
    return bx - slack <= x <= bx + bw + slack and by - slack <= y <= by + bh + slack


def fallback(i):
    return (80 + i * 180, FALLBACK_Y, 160, 70)


# ------------------------------------------------------ Текстовые блоки

def test_text_is_uppercased_and_only_replies_get_soft_hyphens(doc):
    doc.set_translation(lines("- приходить\nприходить\n"))
    reply, sound = doc.blocks
    assert reply.text.replace(SHY, "") == "ПРИХОДИТЬ" and SHY in reply.text
    assert sound.text == "ПРИХОДИТЬ"


def test_default_styles(doc):
    doc.set_translation(lines("- Привет!\nБАЦ!\n"))
    reply, sound = doc.blocks
    assert (reply.shadow, reply.bold, reply.arch) == (False, 0, 0)
    assert (sound.shadow, sound.bold, sound.arch) == (True, 0, 0)  # Звук по умолчанию — Shadow


def block(**kw):
    defaults = dict(text="X", is_reply=True, shadow=False, x=0, y=0, width=100, size=12)
    return TextBlock(**{**defaults, **kw})


def test_shadow_button_means_different_things_for_reply_and_sound():
    """«Shadow / Обычный»: у Реплики — Жирность 0 <-> 2, у Звука — Shadow <-> сплошной."""
    reply, sound = block(is_reply=True), block(is_reply=False, shadow=True)
    reply.toggle_shadow(), sound.toggle_shadow()
    assert (reply.bold, reply.shadow, sound.bold, sound.shadow) == (2, False, 0, False)
    reply.toggle_shadow(), sound.toggle_shadow()
    assert (reply.bold, reply.shadow, sound.bold, sound.shadow) == (0, False, 0, True)


def test_limits():
    b = block()
    b.set_stretch(10), b.set_bold(-3)
    assert (b.stretch, b.bold) == (50, 0)
    b.set_stretch(1000), b.set_bold(99)
    assert (b.stretch, b.bold) == (400, 10)
    b.set_arch(1000)
    assert b.arch == 150
    b.set_arch(-1000)
    assert b.arch == -150


def test_editing_reply_text_rehyphenates():
    b = block(is_reply=True)
    b.set_text("ПРИХОДИТЬ")
    assert b.text == "ПРИ" + SHY + "ХО" + SHY + "ДИТЬ"
    s = block(is_reply=False)
    s.set_text("ПРИХОДИТЬ")
    assert s.text == "ПРИХОДИТЬ"


# ------------------------------------------------- расстановка по местам

def test_replies_fill_bubbles_in_reading_order(doc):
    doc.open_strip(strip("pe1963-04-08"), translation.read(DATA / "pe1963-04-08.txt"))
    replies = [b for b in doc.blocks if b.is_reply]
    for b, box in zip(replies, doc.bubbles):
        assert inside(center(doc, b), box)


def test_extra_reply_goes_to_fallback_row(doc):
    """В 04-08 найдено 3 Бабла, а Реплик 4: четвёртая встаёт в запасной ряд вверху слева."""
    doc.open_strip(strip("pe1963-04-08"), translation.read(DATA / "pe1963-04-08.txt"))
    assert len(doc.bubbles) == 3
    assert inside(center(doc, doc.blocks[3]), fallback(0))


def test_extra_reply_steals_a_sound_slot(doc):
    """ХАРАКТЕРИЗАЦИЯ (вероятно баг): лишняя Реплика сдвигает счётчик Звуков.
    В 04-12 найдено 4 Бабла и 2 Звука; в Переводе 5 Реплик и 2 Звука.
    Пятая Реплика занимает запасное место и «съедает» первый Звук:
    первый Звук встаёт на второе найденное место, второй — в запасной ряд,
    а первое найденное место Звука остаётся пустым."""
    doc.open_strip(strip("pe1963-04-12"), translation.read(DATA / "pe1963-04-12_overflow.txt"))
    assert (len(doc.bubbles), len(doc.sounds)) == (4, 2)
    sounds = [b for b in doc.blocks if not b.is_reply]
    assert inside(center(doc, sounds[0]), doc.sounds[1])
    assert inside(center(doc, sounds[1]), fallback(2))
    assert not any(inside(center(doc, s), doc.sounds[0]) for s in sounds)


def test_sound_inherits_detected_arch(doc):
    doc.open_strip(strip("pe1963-04-10"), lines("БАЦ!\n"))
    assert doc.sounds[0].arch != 0
    assert doc.blocks[0].arch == doc.sounds[0].arch


def test_translation_before_or_after_image_gives_same_blocks(typography):
    a, b = Document(typography), Document(typography)
    a.set_translation(translation.read(DATA / "pe1963-04-08.txt"))
    a.open_strip(strip("pe1963-04-08"))
    b.open_strip(strip("pe1963-04-08"))
    b.set_translation(translation.read(DATA / "pe1963-04-08.txt"))
    assert [block_state(x) for x in a.blocks] == [block_state(x) for x in b.blocks]


def test_without_image_lines_go_to_fallback_row(doc):
    doc.set_translation(lines("- Привет!\nБАЦ!\n"))
    assert doc.image is None
    assert inside(center(doc, doc.blocks[0]), fallback(0))
    assert inside(center(doc, doc.blocks[1]), fallback(1))


def test_image_without_translation_is_cleaned_with_no_blocks(doc):
    doc.open_strip(strip("pe1963-04-08"))
    assert doc.blocks == []
    assert (doc.image == doc.analysis.cleaned).all()
    assert doc.image is not doc.analysis.cleaned


# ------------------------------------------------------------------ отмена

@pytest.fixture
def loaded(doc):
    doc.open_strip(strip("pe1963-04-08"), translation.read(DATA / "pe1963-04-08.txt"))
    return doc


def test_undo_restores_blocks_and_selection(loaded):
    before = [block_state(b) for b in loaded.blocks]
    loaded.checkpoint(selected=[1])
    loaded.blocks[1].size += 2
    loaded.blocks[1].set_italic(True)
    assert loaded.undo() == [1]
    assert [block_state(b) for b in loaded.blocks] == before
    assert loaded.undo() is None


def test_undo_restores_erased_pixels(loaded):
    before = loaded.image.copy()
    loaded.checkpoint()                 # так делает правая кнопка мыши перед Ластиком
    assert loaded.erase_spot(50, 450)
    assert (loaded.image != before).any()
    loaded.undo()
    assert (loaded.image == before).all()


def test_eraser_outside_image_does_nothing(loaded):
    assert not loaded.erase_spot(-5, 10)
    assert not loaded.erase_spot(10_000, 10)


def test_history_keeps_last_40_states(loaded):
    for _ in range(60):
        loaded.checkpoint()
    assert loaded.history_size == 40


def test_dropped_checkpoint_is_forgotten(loaded):
    loaded.checkpoint()
    loaded.drop_checkpoint()
    assert not loaded.can_undo


def test_loading_translation_onto_image_can_be_undone(doc):
    doc.open_strip(strip("pe1963-04-08"))
    doc.set_translation(lines("- Привет!\n"))
    assert len(doc.blocks) == 1
    doc.undo()
    assert doc.blocks == []


def test_new_translation_resets_eraser_edits(loaded):
    loaded.erase_spot(50, 450)
    loaded.set_translation(translation.read(DATA / "pe1963-04-08.txt"))
    assert (loaded.image == loaded.analysis.cleaned).all()


def test_new_strip_starts_history_over_and_keeps_translation(loaded):
    """Новый стрип — новая история: Ctrl+Z не возвращает предыдущий стрип
    (в монолите возвращал: это было побочным эффектом, а не задумкой)."""
    loaded.checkpoint()
    loaded.open_strip(strip("pe1963-04-09"))
    assert not loaded.can_undo
    assert len(loaded.blocks) == 4


def test_remove_blocks(loaded):
    first = loaded.blocks[0]
    loaded.remove([first])
    assert first not in loaded.blocks and len(loaded.blocks) == 3
