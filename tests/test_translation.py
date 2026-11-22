"""Разбор Перевода (.txt): какие строки становятся Репликами, какие Звуками, какие пропускаются."""

SHY = "­"


def parsed(ts):
    return [(b["text"].replace(SHY, ""), b["is_bubble"]) for b in ts.snapshot()]


def write(tmp_path, text, encoding="utf-8"):
    p = tmp_path / "перевод.txt"
    p.write_bytes(text.encode(encoding))
    return p


def test_dash_means_reply_no_dash_means_sound(typesetter, tmp_path):
    txt = write(tmp_path, "- Привет, Чарли Браун!\nХАХАХА!\n- Как дела?\n")
    assert parsed(typesetter.load_txt(txt)) == [
        ("ПРИВЕТ, ЧАРЛИ БРАУН!", True),
        ("ХАХАХА!", False),
        ("КАК ДЕЛА?", True),
    ]


def test_dates_footnotes_comments_and_blank_lines_are_skipped(typesetter, tmp_path):
    txt = write(tmp_path, (
        "1963-04-08\n"
        "- Привет!\n"
        "\n"
        "   \n"
        "* сноска переводчика\n"
        "(комментарий для команды)\n"
        "1963-04-09 строка, начинающаяся с даты, тоже пропадает\n"
        "- Пока!\n"
    ))
    assert parsed(typesetter.load_txt(txt)) == [("ПРИВЕТ!", True), ("ПОКА!", True)]


def test_text_is_uppercased(typesetter, tmp_path):
    txt = write(tmp_path, "- всё отлично\nой-ой\n")
    assert parsed(typesetter.load_txt(txt)) == [("ВСЁ ОТЛИЧНО", True), ("ОЙ-ОЙ", False)]


def test_only_replies_get_soft_hyphens(typesetter, tmp_path):
    txt = write(tmp_path, "- приходить\nприходить\n")
    reply, sound = typesetter.load_txt(txt).snapshot()
    assert SHY in reply["text"]
    assert SHY not in sound["text"]


def test_windows_1251_file_is_read(typesetter, tmp_path):
    txt = write(tmp_path, "- Привет!\nБАЦ!\n", encoding="cp1251")
    assert parsed(typesetter.load_txt(txt)) == [("ПРИВЕТ!", True), ("БАЦ!", False)]


def test_em_dash_is_NOT_a_reply(typesetter, tmp_path):
    """ХАРАКТЕРИЗАЦИЯ: только ASCII-дефис делает строку Репликой.
    Строка с длинным тире «— Привет!» (как принято в русском тексте) становится Звуком."""
    txt = write(tmp_path, "— Привет!\n")
    assert parsed(typesetter.load_txt(txt)) == [("— ПРИВЕТ!", False)]


def test_all_leading_dashes_and_spaces_are_stripped(typesetter, tmp_path):
    txt = write(tmp_path, "- - -Привет!\n")
    assert parsed(typesetter.load_txt(txt)) == [("ПРИВЕТ!", True)]


def test_default_styles(typesetter, tmp_path):
    txt = write(tmp_path, "- Привет!\nБАЦ!\n")
    reply, sound = typesetter.load_txt(txt).snapshot()
    assert (reply["is_outlined"], reply["bold"], reply["arch"]) == (False, 0, 0)
    assert (sound["is_outlined"], sound["bold"], sound["arch"]) == (True, 0, 0)  # Звук по умолчанию — Shadow
