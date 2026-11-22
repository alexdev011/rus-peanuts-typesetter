"""Разбор Перевода (.txt): какие строки становятся Репликами, какие Звуками, какие пропускаются.

Правило: сначала Реплики, потом строка «Звуки:» и Звуки; у всех строк тире.
Без «Звуки:» — старое правило: Звуки — строки без тире в конце файла."""
from rus_peanuts.typesetting import translation


def parsed(text):
    return [(ln.text, ln.is_reply) for ln in translation.parse(text)]


def write(tmp_path, text, encoding="utf-8"):
    p = tmp_path / "перевод.txt"
    p.write_bytes(text.encode(encoding))
    return p


def test_sounds_go_after_the_sounds_line():
    assert parsed("- Привет, Чарли Браун!\n- Как дела?\nЗвуки:\n- БАЦ!\n- ХАХАХА!\n") == [
        ("Привет, Чарли Браун!", True),
        ("Как дела?", True),
        ("БАЦ!", False),
        ("ХАХАХА!", False),
    ]


def test_sounds_line_ignores_case_spaces_and_colon():
    for marker in ("ЗВУКИ", "звуки:", "  Звуки :  ", "Звуки"):
        assert parsed(f"- А\n{marker}\n- БАЦ!\n") == [("А", True), ("БАЦ!", False)], marker


def test_dash_ignores_spaces_and_any_dash_works():
    """Пробелы вокруг тире не важны; длинное тире (Word меняет «-» сам) — тоже тире."""
    assert parsed("-Привет\n-   Как дела?\n   - Пока\n– Ага\n— Угу\n") == [
        ("Привет", True), ("Как дела?", True), ("Пока", True), ("Ага", True), ("Угу", True),
    ]


def test_dash_alone_is_skipped():
    assert parsed("- Привет!\n-\n- Пока!\n") == [("Привет!", True), ("Пока!", True)]


def test_utf8_with_bom_is_read(tmp_path):
    """Блокнот сохраняет UTF-8 с невидимой меткой BOM в начале — первая строка не должна её получить."""
    lines = translation.read(write(tmp_path, "\ufeff- Привет!\n- Пока!\n"))
    assert [(ln.text, ln.is_reply, ln.dash) for ln in lines] == [("Привет!", True, True), ("Пока!", True, True)]


def test_old_files_sounds_are_the_lines_without_dash_at_the_end():
    assert parsed("- Привет, Чарли Браун!\n- Как дела?\nБАЦ!\nХАХАХА!\n") == [
        ("Привет, Чарли Браун!", True),
        ("Как дела?", True),
        ("БАЦ!", False),
        ("ХАХАХА!", False),
    ]


def test_line_without_dash_before_replies_is_a_reply():
    """Крик в Бабле, записанный без тире: после него ещё есть Реплики, значит, это не Звук."""
    lines = translation.parse("Я дома!\n- Крысьня!\n- Нет ничего хуже...\nБАЦ!\n")
    assert [(ln.text, ln.is_reply) for ln in lines] == [
        ("Я дома!", True), ("Крысьня!", True), ("Нет ничего хуже...", True), ("БАЦ!", False),
    ]
    assert [ln.text for ln in translation.replies_without_dash(lines)] == ["Я дома!"]


def test_only_sounds():
    assert parsed("БАЦ!\nБУМ!\n") == [("БАЦ!", False), ("БУМ!", False)]


def test_dates_footnotes_comments_and_blank_lines_are_skipped():
    assert parsed(
        "1963-04-08\n"
        "- Привет!\n"
        "\n"
        "   \n"
        "* сноска переводчика\n"
        "(комментарий для команды)\n"
        "1963-04-09 строка, начинающаяся с даты, тоже пропадает\n"
        "- Пока!\n"
    ) == [("Привет!", True), ("Пока!", True)]


def test_all_leading_dashes_and_spaces_are_stripped():
    assert parsed("- - -Привет!\n") == [("Привет!", True)]


def test_windows_1251_file_is_read(tmp_path):
    lines = translation.read(write(tmp_path, "- Привет!\nБАЦ!\n", encoding="cp1251"))
    assert [(ln.text, ln.is_reply) for ln in lines] == [("Привет!", True), ("БАЦ!", False)]


def test_crlf_file_is_read(tmp_path):
    lines = translation.read(write(tmp_path, "- Привет!\r\nБАЦ!\r\n"))
    assert [(ln.text, ln.is_reply) for ln in lines] == [("Привет!", True), ("БАЦ!", False)]


def test_empty_file_gives_none(tmp_path):
    assert translation.read(write(tmp_path, "")) is None


def test_file_with_only_comments_gives_empty_list(tmp_path):
    assert translation.read(write(tmp_path, "1963-04-08\n* сноска\n")) == []
