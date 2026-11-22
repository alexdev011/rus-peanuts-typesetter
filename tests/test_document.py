"""Документ вёрстки: расстановка Перевода по местам, правки Текстовых блоков, отмена."""
from pathlib import Path

import pytest

from conftest import block_state, fixture_path
from rus_peanuts.typesetting import analysis, translation
from rus_peanuts.typesetting.document import BLACK, FALLBACK_Y, WHITE, Document, TextBlock

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


def test_every_new_block_gets_the_reply_font(doc):
    """Реплики и Звуки ставятся Шрифтом реплик; другой Шрифт выбирают руками."""
    doc.set_translation(lines("- Привет!\nБАЦ!\n"))
    reply, sound = doc.blocks
    assert reply.font == sound.font == "PeanutsRusbyme-Regular"
    assert (reply.bold, reply.arch, sound.bold, sound.arch) == (0, 0, 0, 0)


def block(**kw):
    defaults = dict(text="X", is_reply=True, font="PeanutsRusbyme-Regular", x=0, y=0, width=100, size=12)
    return TextBlock(**{**defaults, **kw})


def test_font_is_set_by_postscript_name():
    b = block()
    b.set_font("MPMangaFontBold")
    assert b.font == "MPMangaFontBold"


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
    """В 04-12 найдено 4 Бабла, а Реплик 5: пятая встаёт в запасной ряд вверху слева."""
    doc.open_strip(strip("pe1963-04-12"), translation.read(DATA / "pe1963-04-12_overflow.txt"))
    assert len(doc.bubbles) == 4
    replies = [b for b in doc.blocks if b.is_reply]
    assert inside(center(doc, replies[4]), fallback(0))


def test_extra_lines_do_not_shift_each_other():
    """Лишняя Реплика не сдвигает Звуки: у каждого типа своя очередь мест."""
    from rus_peanuts.typesetting.analysis import Box, SoundBox
    from rus_peanuts.typesetting.document import assign_places

    bubbles = [Box(0, 0, 10, 10)]
    sounds = [SoundBox(100, 0, 10, 10, 0), SoundBox(200, 0, 10, 10, 0)]
    placed = [box for _, box in assign_places(lines("- А\n- Б\nБАЦ!\nБУМ!\nХРЯСЬ!\n"), bubbles, sounds)]
    assert placed[0] == bubbles[0]
    assert placed[1] == fallback(0)               # лишняя Реплика
    assert placed[2:4] == sounds                  # Звуки — на свои места
    assert placed[4] == fallback(1)               # лишний Звук


def test_sound_gets_the_detected_arch(doc):
    from rus_peanuts.typesetting.analysis import SoundBox

    block = doc.typography.fit(lines("БАЦ!\n")[0], SoundBox(100, 100, 300, 80, 25))
    assert block.arch == 25 and not block.is_reply


def test_arch_is_read_from_letter_centres():
    from rus_peanuts.typesetting.analysis import _read_arch

    xs = range(0, 300, 30)
    smile = [(x, 50 + int(((x - 135) / 135) ** 2 * 20), 20, 30) for x in xs]   # края ниже середины
    assert _read_arch(smile) > 0
    assert _read_arch([(x, 50, 20, 30) for x in xs]) == 0                    # ровная строка


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


def test_undo_restores_painted_pixels(loaded):
    before = loaded.image.copy()
    loaded.checkpoint()                 # так делает холст перед каждым штрихом Карандаша
    assert loaded.paint(50, 450, 50, 450, 12, WHITE)
    assert (loaded.image != before).any()
    loaded.undo()
    assert (loaded.image == before).all()


def test_pencil_paints_a_solid_line_in_white_or_black(doc):
    import numpy as np

    doc.open_strip(np.full((100, 200, 3), 128, np.uint8))
    assert doc.paint(20, 50, 180, 50, 5, BLACK)
    assert (doc.image[45:56, 20:181] == 0).all()                 # сплошная линия толщиной 11 px
    assert (doc.image[50, 14] == 0).all() and (doc.image[50, 13] == 128).all()  # круглый конец
    assert (doc.image[40, 100] == 128).all()                     # выше линии не задето
    assert doc.paint(100, 50, 100, 50, 3, WHITE)                  # точка
    assert (doc.image[47:54, 100] == 255).all()
    assert set(np.unique(doc.image)) == {0, 128, 255}            # без сглаживания


def test_pencil_out_of_reach_does_nothing_but_reaches_the_edge(loaded):
    before = loaded.image.copy()
    assert not loaded.paint(-30, 10, -20, 10, 12, BLACK)
    assert not loaded.paint(10_000, 10, 10_000, 10, 12, BLACK)
    assert (loaded.image == before).all()
    assert loaded.paint(-5, 10, -5, 10, 12, BLACK)                # кисть задевает край стрипа
    assert (loaded.image[10, 0:7] == 0).all()


def test_pencil_without_strip_does_nothing(doc):
    assert not doc.paint(5, 5, 6, 6, 3, BLACK)


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


def test_new_translation_resets_pencil_edits(loaded):
    loaded.paint(50, 450, 80, 450, 12, BLACK)
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
