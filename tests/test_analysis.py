"""Анализ стрипа: какие Баблы и Звуки находятся и как выглядит Очистка.

Эталонные (golden) тесты фиксируют результат как есть; отдельные тесты ниже
описывают, что поиск находит, а что пока пропускает.
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


def overlaps(box, x0, y0, x1, y1):
    x, y, w, h = box[:4]
    return x < x1 and x + w > x0 and y < y1 and y + h > y0


def test_short_and_bold_replies_are_found():
    """Короткая «WOW!» и крупная жирная реплика у самой рамки кадра — тоже Баблы."""
    bubbles = analyze(fixture_path("strips", "pe1963-04-08.png")).bubbles
    assert len(bubbles) == 4
    assert any(overlaps(b, 1130, 0, 1680, 200) for b in bubbles)        # «WOW!» в третьем кадре
    bubbles = analyze(fixture_path("pages", "wpage_101.png")).bubbles
    assert any(overlaps(b, 1612, 787, 2325, 887) for b in bubbles)     # «HAVE YOU EVER SEEN…»


def test_large_letters_of_replies_are_not_sounds():
    """Раньше крупные буквы реплик находились ещё и как Звуки — теперь дублей нет."""
    for name in ("pe1963-04-09.png", "pe1963-04-10.png", "pe1963-04-11.png", "pe1963-04-12.png"):
        assert analyze(fixture_path("strips", name)).sounds == []
    assert analyze(fixture_path("pages", "wpage_101.png")).sounds == []


def test_sounds_on_the_drawing():
    """KLUNK! и SMACK! — Звуки. Пока не находятся: POW! (буквы контуром слиплись с линиями)
    и ZZZ (буквы столбиком)."""
    sounds = analyze(fixture_path("strips", "pe1963-04-14.png")).sounds
    assert len(sounds) == 1 and overlaps(sounds[0], 330, 940, 600, 1010)    # KLUNK!
    result = analyze(fixture_path("pages", "page_102.png"))
    assert len(result.sounds) == 1 and overlaps(result.sounds[0], 1290, 1590, 1500, 1650)  # SMACK!
    places = result.bubbles + result.sounds
    assert not any(overlaps(b, 1287, 1012, 1390, 1075) for b in places)    # POW!


def test_logo_signature_dates_and_page_captions_are_not_places():
    """Логотип PEANUTS и by SCHULZ, подписи SCHULZ, даты, лица и трава, «Page 89» — не места."""
    for folder, name, logo in (("pages", "wpage_101.png", (160, 330, 780, 620)),
                               ("strips", "pe1963-04-14.png", (287, 112, 875, 400))):
        result = analyze(fixture_path(folder, name))
        assert not any(overlaps(b, *logo) for b in result.bubbles + result.sounds)
    result = analyze(fixture_path("pages", "page_100.png"))
    assert len(result.bubbles) == 11 and result.sounds == []               # 11 Баблов, больше ничего
    assert not any(b[1] > 1700 for b in result.bubbles)                    # «Page 89» внизу


def test_bubbles_are_in_reading_order():
    bubbles = analyze(fixture_path("pages", "page_100.png")).bubbles
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
