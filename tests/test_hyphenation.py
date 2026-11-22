"""Переносы в Репликах: мягкий перенос (U+00AD) между слогами."""
import pytest

from rus_peanuts.typesetting.hyphenation import hyphenate_text, hyphenate_word

SHY = "\u00ad"


def show(s):
    return s.replace(SHY, "|")


@pytest.mark.parametrize("word, expected", [
    ("ПРИВЕТ", "ПРИВЕТ"),            # короче 7 букв — не трогаем
    ("ВСТРЕЧ", "ВСТРЕЧ"),
    ("БОЛЬШОЙ", "БОЛЬ|ШОЙ"),
    ("КРЫСЬНЯ", "КРЫСЬ|НЯ"),
    ("СТРАННЫЙ", "СТРАН|НЫЙ"),
    ("ПРИХОДИТЬ", "ПРИ|ХО|ДИТЬ"),
    ("ШОКОЛАДКА", "ШО|КО|ЛАД|КА"),
    ("ПОДЪЕЗДНОЙ", "ПОДЪ|ЕЗ|ДНОЙ"),
    ("ПРИВЕТСТВУЮ", "ПРИ|ВЕТ|СТВУЮ"),
    ("ВСТРЕТИТЬСЯ", "ВСТРЕ|ТИТЬ|СЯ"),
    ("МЕНДЕЛЬСОНА", "МЕН|ДЕЛЬ|СО|НА"),
    ("ЗДРАВСТВУЙТЕ", "ЗДРАВ|СТВУЙ|ТЕ"),
    ("ААААААА", "АА|А|А|А|АА"),      # одни гласные: режет почти по каждой букве
])
def test_hyphenate_word(word, expected):
    assert show(hyphenate_word(word)) == expected


def test_hyphenate_text_touches_only_long_cyrillic_words():
    text = "Привет, ПРИХОДИТЬ hello-world ВСТРЕТИТЬСЯ!"
    assert show(hyphenate_text(text)) == "Привет, ПРИ|ХО|ДИТЬ hello-world ВСТРЕ|ТИТЬ|СЯ!"


def test_soft_hyphens_are_invisible_in_plain_text():
    assert hyphenate_text("ПРИХОДИТЬ").replace(SHY, "") == "ПРИХОДИТЬ"
