"""Набор шрифтов: шрифты из папки программы, их PostScript-имена и добавление новых."""
import pytest

from conftest import ROOT
from rus_peanuts.typesetting.fonts import DEFAULT_FONT, FALLBACK_FAMILY, load_fonts

FONTS = ROOT / "fonts"


@pytest.fixture
def library(qt_app, tmp_path):
    return load_fonts(search_dirs=[str(FONTS)], folder=str(tmp_path / "fonts"))


def test_fonts_folder_becomes_the_font_set(library):
    assert {f.postscript: f.name for f in library.faces} == {
        "PeanutsRusbyme-Regular": "Peanuts by me",
        "MPMangaFontBold-Bold": "MPMangaFont-Bold",
        "MPMangaFontBold": "Mp Manga Bold Shadow",
    }
    assert [f.name for f in library.faces] == sorted((f.name for f in library.faces), key=str.lower)


def test_each_font_has_its_own_qt_family(library):
    """MP Manga Bold и MP Manga Bold Shadow — одно семейство внутри файлов; в Qt их нельзя путать."""
    families = [f.family for f in library.faces]
    assert len(set(families)) == len(families)


def test_qt_family_names_are_neutral(library):
    """Windows отрезает от имени семейства слова вроде «-Bold»: MP Manga Bold и MP Manga Bold Shadow
    сливались в одно семейство, и Shadow рисовался сплошным. Имена семейств не должны быть
    продолжением друг друга и не должны содержать названий начертаний."""
    families = [f.family for f in library.faces]
    for a in families:
        assert not any(w in a.lower() for w in ("bold", "italic", "regular", "light", "black", "shadow"))
        assert not any(b != a and b.startswith(a) for b in families)


def test_unknown_font_is_shown_with_the_reply_font(library):
    assert library.default == DEFAULT_FONT
    assert library.family("TroubleSide") == library.get(DEFAULT_FONT).family


def test_empty_font_set_falls_back_to_a_system_font(qt_app, tmp_path):
    library = load_fonts(search_dirs=[str(tmp_path)], folder=str(tmp_path))
    assert library.faces == []
    assert library.family(DEFAULT_FONT) == FALLBACK_FAMILY


def test_install_copies_font_into_the_folder(library, tmp_path):
    import shutil

    src = tmp_path / "source" / "My Shadow.ttf"
    src.parent.mkdir()
    shutil.copyfile(FONTS / "Mp Manga Bold Shadow.ttf", src)
    face = library.install(str(src))
    assert face.postscript == "MPMangaFontBold"             # уже был в Наборе — тот же шрифт
    assert (tmp_path / "fonts" / "My Shadow.ttf").exists()


def test_install_rejects_non_fonts_without_copying(library, tmp_path):
    bad = tmp_path / "notes.ttf"
    bad.write_bytes(b"not a font at all")
    assert library.install(str(bad)) is None
    assert not (tmp_path / "fonts").exists()


@pytest.mark.parametrize("fname", sorted(p.name for p in FONTS.glob("*.ttf")))
def test_renamed_font_is_accepted_by_windows_gdi(fname):
    """GDI (движок шрифтов Qt 5 и Qt 6 до 6.8) молча отвергает шрифт без записи 3 в таблице name —
    в сборке для Windows 8.1 весь текст был бы Comic Sans. Проверяем прямо через GDI."""
    import ctypes
    import sys
    from ctypes import wintypes

    from rus_peanuts.typesetting.fonts import rename_ttf_family

    if sys.platform != "win32":
        pytest.skip("GDI есть только в Windows")
    data = rename_ttf_family((FONTS / fname).read_bytes(), "RusPeanutsFace001")
    gdi = ctypes.windll.gdi32
    gdi.AddFontMemResourceEx.restype = wintypes.HANDLE
    gdi.RemoveFontMemResourceEx.argtypes = [wintypes.HANDLE]
    count = wintypes.DWORD(0)
    handle = gdi.AddFontMemResourceEx(ctypes.create_string_buffer(data, len(data)), len(data), None,
                                      ctypes.byref(count))
    assert handle, "GDI не принял переименованный шрифт"
    gdi.RemoveFontMemResourceEx(handle)
