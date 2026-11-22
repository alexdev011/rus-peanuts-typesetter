"""Анализ стрипа: какие Баблы и Звуки находятся и как выглядит Очистка.

Это эталонные (golden) тесты: они фиксируют результат как есть, включая
известные промахи (см. test_known_detection_gaps).
"""
import pytest

from conftest import fixture_path
from rus_peanuts.typesetting import analysis


def analyze(path):
    return analysis.analyze(analysis.load_image(path))


IMAGES = [
    ("strips", f"pe1963-04-{d:02d}.png") for d in range(8, 15)
] + [
    ("pages", "page_100.png"),
    ("pages", "page_102.png"),
    ("pages", "wpage_101.png"),
]


@pytest.mark.parametrize("folder, name", IMAGES, ids=[n for _, n in IMAGES])
def test_analysis_matches_golden(golden, folder, name):
    result = analyze(fixture_path(folder, name))
    g = golden()
    g.check({
        "size": list(result.original.shape),
        "bubbles": [list(b) for b in result.bubbles],
        "sounds": [list(s) for s in result.sounds],  # x, y, w, h, Изгиб
        "cleaned": g.image("cleaned", result.cleaned),
    })


def test_unreadable_file_is_none(tmp_path):
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"not an image")
    assert analysis.load_image(bad) is None


def test_original_is_not_modified_by_cleaning():
    img = analysis.load_image(fixture_path("strips", "pe1963-04-08.png"))
    before = img.copy()
    result = analysis.analyze(img)
    assert (img == before).all()
    assert (result.cleaned != before).any()


def test_known_detection_gaps():
    """ХАРАКТЕРИЗАЦИЯ известных промахов на сканах ~2200 px шириной:
    * короткая реплика «WOW!» (меньше 6 букв) не находится как Бабл;
    * крупные буквы обычных реплик дополнительно находятся как Звуки.
    """
    bubbles = analyze(fixture_path("strips", "pe1963-04-08.png")).bubbles
    assert len(bubbles) == 3  # в стрипе 4 бабла, «WOW!» потерян
    wow_panel = (1130, 1680)   # x-диапазон третьего кадра
    assert not any(wow_panel[0] <= b[0] <= wow_panel[1] for b in bubbles)

    sounds = analyze(fixture_path("strips", "pe1963-04-09.png")).sounds
    assert len(sounds) == 2  # в стрипе нет ни одного Звука — это обычные реплики


def test_bubbles_are_in_reading_order():
    bubbles = analyze(fixture_path("pages", "page_100.png")).bubbles
    # ХАРАКТЕРИЗАЦИЯ: подпись страницы сборника «Page 89» внизу тоже находится как Бабл
    footer = [b for b in bubbles if b[1] > 1700]
    assert len(footer) == 1
    bubbles = [b for b in bubbles if b not in footer]
    rows = []
    for b in bubbles:
        if rows and abs(b[1] - rows[-1][-1][1]) < 150:
            rows[-1].append(b)
        else:
            rows.append([b])
    assert len(rows) == 3  # три Ежедневных стрипа на Странице
    for row in rows:
        xs = [b[0] for b in row]
        assert xs == sorted(xs)
