"""Анализ стрипа: какие Баблы и Звуки находятся и как выглядит Очистка.

Это эталонные (golden) тесты: они фиксируют результат как есть, включая
известные промахи (см. test_known_detection_gaps).
"""
import pytest

from conftest import fixture_path

IMAGES = [
    ("strips", f"pe1963-04-{d:02d}.png") for d in range(8, 15)
] + [
    ("pages", "page_100.png"),
    ("pages", "page_102.png"),
    ("pages", "wpage_101.png"),
]


@pytest.mark.parametrize("folder, name", IMAGES, ids=[n for _, n in IMAGES])
def test_analysis_matches_golden(ct, golden, folder, name):
    path = fixture_path(folder, name)
    img, erase_mask, bubbles, sounds = ct.analyze_strip_universal(str(path))
    g = golden()
    cleaned = ct.clean_selected_bubbles(img, erase_mask, bubbles + sounds)
    g.check({
        "size": list(img.shape),
        "bubbles": [list(map(int, b)) for b in bubbles],
        "sounds": [list(map(int, s)) for s in sounds],  # x, y, w, h, Изгиб
        "erase_mask": g.image("erase_mask", erase_mask),
        "cleaned": g.image("cleaned", cleaned),
    })


def test_unreadable_file_returns_empty(ct, tmp_path):
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"not an image")
    assert ct.analyze_strip_universal(str(bad)) == (None, None, [], [])


def test_known_detection_gaps(ct):
    """ХАРАКТЕРИЗАЦИЯ известных промахов на сканах ~2200 px шириной:
    * короткая реплика «WOW!» (меньше 6 букв) не находится как Бабл;
    * крупные буквы обычных реплик дополнительно находятся как Звуки.
    """
    _, _, bubbles, sounds = ct.analyze_strip_universal(str(fixture_path("strips", "pe1963-04-08.png")))
    assert len(bubbles) == 3  # в стрипе 4 бабла, «WOW!» потерян
    wow_panel = (1130, 1680)   # x-диапазон третьего кадра
    assert not any(wow_panel[0] <= b[0] <= wow_panel[1] for b in bubbles)

    _, _, bubbles, sounds = ct.analyze_strip_universal(str(fixture_path("strips", "pe1963-04-09.png")))
    assert len(sounds) == 2  # в стрипе нет ни одного Звука — это обычные реплики


def test_bubbles_are_in_reading_order(ct):
    _, _, bubbles, _ = ct.analyze_strip_universal(str(fixture_path("pages", "page_100.png")))
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
