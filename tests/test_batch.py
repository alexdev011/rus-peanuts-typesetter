"""Пачка: папка Оригиналов и один Файл перевода с Переводами по датам."""
import shutil

import pytest

from conftest import fixture_path
from rus_peanuts.typesetting import project, translation
from rus_peanuts.typesetting.batch import Batch, strip_date

FILE = """1963-04-08
- Покупка пластинок поднимает мне настроение...
-Сегодня мне было так грустно...
-  Ого!
- Насколько же можно грустить?

1963-04-09 вторник
-Привет!
Звуки:
- БАЦ!

1963-04-20
- Перевод без стрипа

1963-04-08
- Повтор даты
"""


@pytest.fixture
def folder(tmp_path):
    """Папка Пачки: три датированных стрипа, один без даты и посторонний файл."""
    d = tmp_path / "стрипы"
    d.mkdir()
    for day in ("08", "09", "10"):
        shutil.copy(fixture_path("strips", f"pe1963-04-{day}.png"), d / f"pe1963-04-{day}.png")
    shutil.copy(fixture_path("strips", "pe1963-04-11.png"), d / "page_100 0.png")
    (d / "заметки.txt").write_text("не стрип", encoding="utf-8")
    txt = tmp_path / "перевод.txt"
    txt.write_text(FILE, encoding="utf-8")
    return d, txt


@pytest.fixture
def batch(folder, typography):
    d, txt = folder
    return Batch(d, typography, txt)


def plain(block):
    return block.text.replace("­", "")  # без мягких переносов


def test_strip_date_from_file_name():
    assert strip_date("pe1963-04-08.png") == "1963-04-08"
    assert strip_date("C:/стрипы/1963-04-08 копия.jpeg") == "1963-04-08"
    assert strip_date("page_100 0.png") is None


def test_strips_of_the_folder_in_name_order(batch):
    assert [(s.name, s.date) for s in batch.strips] == [
        ("page_100 0", None), ("pe1963-04-08", "1963-04-08"), ("pe1963-04-09", "1963-04-09"),
        ("pe1963-04-10", "1963-04-10"),
    ]


def test_problems_list_what_does_not_match(batch):
    p = batch.problems()
    assert p.no_date == ["page_100 0"]
    assert p.no_translation == ["pe1963-04-10"]
    assert p.no_strip == ["1963-04-20"]
    assert p.duplicates == ["1963-04-08"]


def test_each_strip_gets_its_own_translation(batch):
    doc = batch.open(1)
    assert [plain(b)[:7] for b in doc.blocks] == ["ПОКУПКА", "СЕГОДНЯ", "ОГО!", "НАСКОЛЬ"]
    doc = batch.open(2)
    assert [(plain(b), b.is_reply) for b in doc.blocks] == [("ПРИВЕТ!", True), ("БАЦ!", False)]
    assert batch.open(3).blocks == [] and batch.open(0).blocks == []     # нет Перевода / нет даты


def test_untouched_strip_is_rebuilt_from_the_file_edited_is_kept(batch, folder):
    _, txt = folder
    doc = batch.open(2)
    batch.leave(2)
    assert batch.strips[2].document is None                               # не правили — не держим
    txt.write_text(FILE.replace("-Привет!", "- Здравствуй!"), encoding="utf-8")
    assert plain(batch.open(2).blocks[0]) == "ЗДРАВСТВУЙ!"                # файл перечитан
    doc = batch.open(1)
    doc.checkpoint()
    doc.blocks[0].x += 50
    batch.leave(1)
    assert batch.open(1) is doc and batch.unsaved() == [batch.strips[1]]


def test_new_translation_file_resets_only_untouched_strips(batch, tmp_path):
    edited = batch.open(1)
    edited.checkpoint()
    batch.open(2)
    other = tmp_path / "другой.txt"
    other.write_text("1963-04-09\n- Другой\n", encoding="utf-8")
    batch.set_translation(other)
    assert batch.strips[1].document is edited
    assert batch.strips[2].document is None
    assert plain(batch.open(2).blocks[0]) == "ДРУГОЙ"


def test_save_all_writes_png_and_project_per_strip(batch, tmp_path, typography):
    doc = batch.open(1)
    doc.checkpoint()
    doc.blocks[0].x += 50
    out = tmp_path / "result"
    assert batch.save_all(out) == []
    names = sorted(p.name for p in out.iterdir())
    assert names == sorted(f"{s.name}{ext}" for s in batch.strips for ext in (".png", project.EXTENSION))
    assert batch.unsaved() == [] and all(s.saved for s in batch.strips)
    restored = project.load(out / f"pe1963-04-08{project.EXTENSION}", typography)
    assert restored.blocks[0].x == doc.blocks[0].x                      # ручная правка попала в проект


def test_translation_file_with_dates():
    tf = translation.parse_file(FILE)
    assert tf.dates == ["1963-04-08", "1963-04-09", "1963-04-20"]
    assert [ln.text for ln in tf.for_date("1963-04-08")] == [
        "Покупка пластинок поднимает мне настроение...", "Сегодня мне было так грустно...", "Ого!",
        "Насколько же можно грустить?"]
    assert tf.only() is None and tf.undated is None


def test_lines_before_the_first_date_are_skipped_and_no_dates_means_one_translation():
    tf = translation.parse_file("- Что-то до даты\n1963-04-08\n- Привет\n")
    assert tf.dates == ["1963-04-08"] and [ln.text for ln in tf.only()] == ["Привет"]
    tf = translation.parse_file("- Привет\n- Пока\n")
    assert tf.dates == [] and [ln.text for ln in tf.only()] == ["Привет", "Пока"]


# --------------------------------------------------------------------- окно

@pytest.fixture
def window_batch(typesetter, folder, monkeypatch):
    """Окно с открытой Пачкой; сообщения окна собираются в список."""
    from rus_peanuts.ui import main_window

    d, txt = folder
    shown = []
    monkeypatch.setattr(main_window.QMessageBox, "information", staticmethod(lambda *a, **k: shown.append(a[2])))
    typesetter.win.load_txt(str(txt))
    typesetter.win.open_folder(str(d))
    typesetter.shown = shown
    return typesetter


def test_window_opens_folder_and_walks_strips(window_batch):
    win = window_batch.win
    assert not win.batch_panel.isHidden() and win.list_strips.count() == 4
    assert win.act_save_all.isEnabled()
    assert "Переводы без стрипа: 1963-04-20" in window_batch.shown[0]       # о несовпадениях сказали
    assert win.lbl_status.text().startswith("page_100 0: в имени нет даты")
    win.btn_next.click()
    assert win.strip_name == "pe1963-04-08" and len(win.items) == 4
    assert win.lbl_batch.text() == "2 из 4"
    assert "нет перевода" in win.list_strips.item(3).text()


def test_edits_are_kept_between_strips_and_marked(window_batch):
    win = window_batch.win
    win.step_strip(1)
    win.checkpoint()
    win.items[0].setPos(win.items[0].pos().x() + 40, win.items[0].pos().y())
    doc, x = win.document, win.items[0].block.x
    assert win.list_strips.item(1).text().endswith("●")
    win.step_strip(1)
    win.step_strip(-1)
    assert win.document is doc and win.items[0].block.x == x


def test_save_all_from_window(window_batch, tmp_path, monkeypatch):
    from rus_peanuts.ui import main_window

    out = tmp_path / "готово"
    out.mkdir()
    monkeypatch.setattr(main_window.QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(out)))
    window_batch.win.save_all()
    assert len(list(out.glob("*.png"))) == 4 and len(list(out.glob(f"*{project.EXTENSION}"))) == 4
    assert all(window_batch.win.list_strips.item(k).text().split("  ")[0].endswith("✓") for k in range(4))
    assert window_batch.shown[-1].startswith("Сохранено стрипов: 4 из 4")



def test_save_all_offers_the_multitool_result_folder(window_batch, tmp_path, monkeypatch):
    from rus_peanuts.ui import main_window

    monkeypatch.chdir(tmp_path)
    asked = []
    monkeypatch.setattr(main_window.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda parent, title, path: asked.append(path) or ""))
    window_batch.win.save_all()
    assert asked == [str(tmp_path / "result")]

def test_leaving_batch_with_unsaved_edits_asks(window_batch, monkeypatch):
    from rus_peanuts.ui import main_window

    win = window_batch.win
    win.step_strip(1)
    win.checkpoint()
    answer = [main_window.QMessageBox.StandardButton.No]
    monkeypatch.setattr(main_window.QMessageBox, "question", staticmethod(lambda *a, **k: answer[0]))
    win.load_image(str(fixture_path("strips", "pe1963-04-12.png")))
    assert win.batch is not None                                         # передумали — Пачка на месте
    answer[0] = main_window.QMessageBox.StandardButton.Yes
    win.load_image(str(fixture_path("strips", "pe1963-04-12.png")))
    assert win.batch is None and win.batch_panel.isHidden() and win.strip_name == "pe1963-04-12"


def test_closing_with_unsaved_edits_can_be_cancelled(window_batch, monkeypatch):
    from qtpy.QtGui import QCloseEvent
    from rus_peanuts.ui import main_window

    win = window_batch.win
    win.step_strip(1)
    win.checkpoint()
    monkeypatch.setattr(main_window.QMessageBox, "question",
                        staticmethod(lambda *a, **k: main_window.QMessageBox.StandardButton.No))
    event = QCloseEvent()
    win.closeEvent(event)
    assert not event.isAccepted()


def test_single_strip_without_date_asks_which_translation(typesetter, folder, monkeypatch):
    from rus_peanuts.ui import main_window

    d, txt = folder
    monkeypatch.setattr(main_window.QInputDialog, "getItem", staticmethod(lambda *a, **k: ("1963-04-09", True)))
    typesetter.win.load_txt(str(txt))
    typesetter.win.load_image(str(d / "page_100 0.png"))
    assert [(plain(b), b.is_reply) for b in typesetter.doc.blocks] == [("ПРИВЕТ!", True), ("БАЦ!", False)]


def test_single_strip_takes_its_date_from_a_many_dates_file(typesetter, folder):
    d, txt = folder
    typesetter.win.load_txt(str(txt))
    typesetter.win.load_image(str(d / "pe1963-04-09.png"))
    assert [plain(b) for b in typesetter.doc.blocks] == ["ПРИВЕТ!", "БАЦ!"]
    typesetter.win.load_image(str(d / "pe1963-04-10.png"))
    assert typesetter.doc.blocks == []
    assert typesetter.win.lbl_status.text().startswith("В файле перевода нет Перевода на 1963-04-10.")
