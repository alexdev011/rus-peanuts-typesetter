"""Разбор Перевода (.txt): какие строки становятся Репликами, какие Звуками, какие пропускаются."""
from rus_peanuts.typesetting import translation


def parsed(text):
    return [(ln.text, ln.is_reply) for ln in translation.parse(text)]


def write(tmp_path, text, encoding="utf-8"):
    p = tmp_path / "перевод.txt"
    p.write_bytes(text.encode(encoding))
    return p


def test_dash_means_reply_no_dash_means_sound():
    assert parsed("- Привет, Чарли Браун!\nХАХАХА!\n- Как дела?\n") == [
        ("Привет, Чарли Браун!", True),
        ("ХАХАХА!", False),
        ("Как дела?", True),
    ]


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


def test_em_dash_is_NOT_a_reply():
    """ХАРАКТЕРИЗАЦИЯ: только ASCII-дефис делает строку Репликой.
    Строка с длинным тире «— Привет!» (как принято в русском тексте) становится Звуком."""
    assert parsed("— Привет!\n") == [("— Привет!", False)]


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
