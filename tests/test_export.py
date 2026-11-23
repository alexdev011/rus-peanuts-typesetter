"""Экспорт: PNG и PSD (текстовые слои Фотошопа по сценарию JSX)."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import fixture_path, qt6_metrics
from rus_peanuts.export import psd
from rus_peanuts.export.png import export_png
from rus_peanuts.typesetting import analysis, translation

DATA = Path(__file__).parent / "data"
MOCK = Path(__file__).parent / "js" / "photoshop_mock.js"


@pytest.fixture
def loaded(doc):
    doc.open_strip(analysis.load_image(fixture_path("strips", "pe1963-04-08.png")),
                   translation.read(DATA / "pe1963-04-08.txt").only())
    return doc


# --------------------------------------------------------------------- PNG

def test_png_needs_a_strip(doc, tmp_path):
    assert not export_png(doc, doc.typography, tmp_path / "x.png")


def test_png_has_strip_size(loaded, tmp_path):
    import cv2

    out = tmp_path / "out.png"
    assert export_png(loaded, loaded.typography, out)
    assert cv2.imread(str(out)).shape[:2] == loaded.image.shape[:2]


# --------------------------------------------------------- слои для Фотошопа

@qt6_metrics
def test_text_layer_keeps_program_line_breaks(loaded):
    layer = psd.text_layer(loaded.blocks[0], loaded.typography)
    assert layer.contents.split("\r") == [
        "ПОКУПКА ПЛАСТИ-", "НОК ПОДНИМАЕТ", "МНЕ НАСТРОЕНИЕ...",
        "КОГДА МНЕ ГРУС-", "ТНО, Я ПОКУПАЮ", "НОВЫЕ ПЛАСТИНКИ..",
    ]
    assert "\u00ad" not in layer.contents


def test_text_layer_geometry_matches_qt_layout(loaded):
    block = loaded.blocks[0]
    st = loaded.typography.set_text(block)
    layer = psd.text_layer(block, loaded.typography)
    assert layer.size == round(block.size * 96 / 72, 2)
    assert layer.leading == round(st.leading_px, 2)
    assert layer.x == round(block.x + st.lines[0].center_x, 2)
    assert layer.y == round(block.y + st.lines[0].baseline_y, 2)
    assert (layer.hscale, layer.italic, layer.stroke, layer.warp) == (100, False, 0, 0)


def test_layer_font_is_the_block_font(doc):
    """Фотошоп находит шрифт по PostScript-имени — тому же, что хранится в блоке."""
    doc.set_translation(translation.parse("- Привет!\nБАЦ!\nБУМ!\n"))
    doc.blocks[1].set_font("MPMangaFontBold")
    doc.blocks[2].set_font("TroubleSide")  # шрифта нет в программе — в PSD имя всё равно уходит
    names = [psd.text_layer(b, doc.typography).font for b in doc.blocks]
    assert names == ["PeanutsRusbyme-Regular", "MPMangaFontBold", "TroubleSide"]


def test_styles_become_photoshop_effects(loaded):
    b = loaded.blocks[2]
    b.bold, b.italic, b.stretch = 3, True, 130
    b.set_arch(10)
    layer = psd.text_layer(b, loaded.typography)
    assert layer.stroke == max(1, round(loaded.typography.bold_pen_width(b) / 2))
    assert layer.italic and layer.hscale == 130
    assert 0 < layer.warp <= 100
    b.set_arch(-150)
    assert psd.text_layer(b, loaded.typography).warp == -100


# ------------------------------------------------------------ задание и JSX

def test_prepare_writes_job_folder(loaded, tmp_path):
    job = psd.prepare(loaded, loaded.typography, tmp_path / "out.psd", workdir=tmp_path / "job")
    assert {p.name for p in job.workdir.iterdir()} == {"background.png", "original.png", "build_psd.jsx"}
    text = job.script.read_text(encoding="utf-8-sig")
    assert "__DATA__" not in text
    data = json.loads(text[text.index("var DATA = ") + 11:text.index(";\n", text.index("var DATA = "))])
    assert data["output"] == (tmp_path / "out.psd").resolve().as_posix()
    assert len(data["layers"]) == len(loaded.blocks)
    assert data["originalName"] == "Оригинал"
    assert all(ord(c) < 128 for c in json.dumps(data, ensure_ascii=True))


def test_prepare_without_strip_fails(doc, tmp_path):
    with pytest.raises(ValueError):
        psd.prepare(doc, doc.typography, tmp_path / "out.psd")


def test_photoshop_command_escapes_quotes(tmp_path):
    job = psd.PsdJob(tmp_path / "a.psd", tmp_path, tmp_path / "it's.jsx", tmp_path / "log")
    cmd = psd.photoshop_command(job)
    assert cmd[0] == "powershell"
    assert "it''s.jsx" in cmd[-1]


def test_result_reads_log(tmp_path):
    job = psd.PsdJob(tmp_path / "a.psd", tmp_path, tmp_path / "s.jsx", tmp_path / "photoshop.log")
    assert psd.result(job)[0] is False
    job.log.write_text("ERROR: шрифт не найден\n", encoding="utf-8")
    assert psd.result(job) == (False, "ERROR: шрифт не найден")
    job.log.write_text("WARN: font X: missing\nOK\n", encoding="utf-8")
    job.psd_path.write_bytes(b"8BPS")
    assert psd.result(job) == (True, "WARN: font X: missing")


# --------------------------------------------- сценарий в поддельном Фотошопе

@pytest.fixture
def node():
    exe = shutil.which("node")
    if not exe:
        pytest.skip("нет Node.js — сценарий JSX не проверить без Фотошопа")
    return exe


def run_mock(node, job):
    out = subprocess.run([node, str(MOCK), str(job.script)], capture_output=True, text=True,
                         encoding="utf-8", check=True)
    return json.loads(out.stdout)


def test_script_builds_layers_and_saves(node, loaded, tmp_path):
    loaded.blocks[0].bold = 3
    loaded.blocks[2].set_arch(20)
    job = psd.prepare(loaded, loaded.typography, tmp_path / "out.psd", workdir=tmp_path / "job")
    state = run_mock(node, job)

    assert state["opened"] == [(job.workdir / "background.png").resolve().as_posix(),
                               (job.workdir / "original.png").resolve().as_posix()]
    assert state["saved"]["path"] == job.psd_path.as_posix()
    assert state["saved"]["layersOption"] is True and state["saved"]["asCopy"] is True
    # снизу вверх: Фон, скрытый Оригинал, тексты в порядке блоков
    stack = list(reversed(state["saved"]["stack"]))
    assert stack[:2] == ["Фон", "Оригинал"] and len(stack) == 2 + len(loaded.blocks)
    assert {c["mode"] for c in state["closed"]} == {"DONOTSAVECHANGES"} and len(state["closed"]) == 2

    expected = [psd.text_layer(b, loaded.typography) for b in loaded.blocks]
    for got, exp in zip(state["layers"], expected):
        t = got["text"]
        assert got["kind"] == "TEXT"
        assert (t["contents"], t["font"], t["size"], t["leading"]) == (exp.contents, exp.font, exp.size, exp.leading)
        assert t["position"] == [exp.x, exp.y]
        assert t["justification"] == "CENTER" and t["useAutoLeading"] is False
        assert t["color"]["rgb"] == {"red": 0, "green": 0, "blue": 0}
    assert state["layers"][2]["text"]["warpStyle"] == "ARC"
    assert state["layers"][2]["text"]["warpBend"] == expected[2].warp
    assert "warpStyle" not in state["layers"][0]["text"]
    assert state["strokes"] == [{"layer": 0, "size": expected[0].stroke}]
    # настройки Фотошопа возвращаются как были
    assert state["prefs"] == {"rulerUnits": "CM", "typeUnits": "POINTS", "displayDialogs": "ALL"}
    assert job.log.read_text(encoding="utf-8").strip() == "OK"


def test_script_without_original_layer(node, loaded, tmp_path):
    job = psd.prepare(loaded, loaded.typography, tmp_path / "out.psd", workdir=tmp_path / "job",
                      with_original=False)
    state = run_mock(node, job)
    assert len(state["opened"]) == 1
    assert "Оригинал" not in state["saved"]["stack"]


# ------------------------------------------------------ настоящий Фотошоп

@pytest.mark.skipif(os.environ.get("RUN_PHOTOSHOP") != "1",
                    reason="запускает настоящий Фотошоп: RUN_PHOTOSHOP=1 pytest tests/test_export.py")
def test_real_photoshop_builds_editable_text(loaded, tmp_path):
    from psd_tools import PSDImage

    ok, message, job = psd.export_psd(loaded, loaded.typography, tmp_path / "out.psd")
    assert ok, message
    layers = list(PSDImage.open(job.psd_path).descendants())
    texts = [la for la in layers if la.kind == "type"]
    assert [la.text for la in texts] == [psd.text_layer(b, loaded.typography).contents for b in loaded.blocks]
    assert {str(la.resource_dict["FontSet"][0]["Name"]).strip("'") for la in texts} == {"PeanutsRusbyme-Regular"}
    original = next(la for la in layers if la.name == "Оригинал")
    assert not original.visible


# --------------------------------------------------------------- окно

def test_window_psd_button_runs_job_and_reports(typesetter, tmp_path, monkeypatch):
    """Кнопка «Экспорт в PSD»: готовит задание и ждёт процесс; вместо Фотошопа — заглушка."""
    import sys

    from qtpy.QtTest import QTest
    from rus_peanuts.ui import main_window

    ts = typesetter.load_image(fixture_path("strips", "pe1963-04-08.png")).load_txt(DATA / "pe1963-04-08.txt")
    out = tmp_path / "out.psd"
    shown = []
    monkeypatch.setattr(main_window.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out), "")))
    monkeypatch.setattr(main_window.QMessageBox, "information", staticmethod(lambda *a, **k: shown.append(a[2])))
    monkeypatch.setattr(main_window.QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append("FAIL " + a[2])))

    def fake_photoshop(job):
        code = ("from pathlib import Path; import sys; "
                "Path(sys.argv[1]).write_text('OK', encoding='utf-8'); Path(sys.argv[2]).write_bytes(b'8BPS')")
        return [sys.executable, "-c", code, str(job.log), str(job.psd_path)]

    monkeypatch.setattr(main_window.psd, "photoshop_command", fake_photoshop)
    ts.win.act_export_psd.trigger()
    assert not ts.win.act_export_psd.isEnabled()
    for _ in range(200):
        if ts.win.psd_process is None:
            break
        QTest.qWait(50)
    assert ts.win.act_export_psd.isEnabled()
    assert shown and str(out) in shown[0]
    assert ts.win.lbl_status.text() == "PSD сохранён: out.psd"
