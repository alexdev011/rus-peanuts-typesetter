"""Файл проекта: сохранить вёрстку и открыть её снова — со всеми правками."""
import json
import zipfile
from pathlib import Path

import pytest

from conftest import block_state, fixture_path
from rus_peanuts.typesetting import analysis, project, translation

DATA = Path(__file__).parent / "data"


@pytest.fixture
def edited(doc):
    """Документ с типичными ручными правками: размер, курсив, Изгиб, Жирность, Шрифт, Карандаш."""
    doc.open_strip(analysis.load_image(fixture_path("strips", "pe1963-04-12.png")),
                   translation.read(DATA / "pe1963-04-12_overflow.txt"))
    doc.blocks[0].size += 3
    doc.blocks[0].set_italic(True)
    doc.blocks[1].x += 40.5
    doc.blocks[2].set_text("ДРУГОЙ ТЕКСТ РЕПЛИКИ")
    doc.blocks[5].set_arch(-35)
    doc.blocks[6].set_bold(1)
    doc.blocks[6].set_font("MPMangaFontBold")
    doc.paint(100, 100, 140, 120, 6, (0, 0, 0))
    doc.remove([doc.blocks[3]])
    return doc


def test_round_trip_keeps_everything(edited, typography, tmp_path):
    path = tmp_path / "стрип.rpeanuts"
    project.save(edited, path)
    restored = project.load(path, typography)

    assert [block_state(b) for b in restored.blocks] == [block_state(b) for b in edited.blocks]
    assert (restored.image == edited.image).all()
    assert (restored.original == edited.original).all()
    assert (restored.analysis.cleaned == edited.analysis.cleaned).all()
    assert restored.bubbles == edited.bubbles and restored.sounds == edited.sounds
    assert restored.lines == edited.lines
    assert not restored.can_undo  # история в файл не попадает


def test_restored_project_can_be_retranslated_like_the_original(edited, typography, tmp_path):
    path = tmp_path / "p.rpeanuts"
    project.save(edited, path)
    restored = project.load(path, typography)
    lines = translation.parse("- Новая реплика\nБАЦ!\n")
    edited.set_translation(lines)
    restored.set_translation(lines)
    assert [block_state(b) for b in restored.blocks] == [block_state(b) for b in edited.blocks]
    assert restored.undo() is not None  # перевод поверх открытого проекта можно отменить


def test_project_without_translation(doc, typography, tmp_path):
    doc.open_strip(analysis.load_image(fixture_path("strips", "pe1963-04-08.png")))
    project.save(doc, tmp_path / "p.rpeanuts")
    restored = project.load(tmp_path / "p.rpeanuts", typography)
    assert restored.lines is None and restored.blocks == []


def test_cannot_save_empty_document(doc, tmp_path):
    with pytest.raises(project.ProjectError):
        project.save(doc, tmp_path / "p.rpeanuts")


def test_file_layout_is_readable_zip(edited, tmp_path):
    path = tmp_path / "p.rpeanuts"
    project.save(edited, path)
    with zipfile.ZipFile(path) as z:
        assert set(z.namelist()) == {"project.json", "original.png", "cleaned.png", "image.png"}
        meta = json.loads(z.read("project.json"))
    assert (meta["format"], meta["version"]) == ("rus-peanuts-project", 2)
    assert [b["font"] for b in meta["blocks"]].count("MPMangaFontBold") == 1


def test_version_1_project_gets_fonts_from_shadow_flag(edited, typography, tmp_path):
    """Проект версии 1: у блоков флаг Shadow вместо Шрифта."""
    src, dst = tmp_path / "v2.rpeanuts", tmp_path / "v1.rpeanuts"
    project.save(edited, src)
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
        for name in zin.namelist():
            data = zin.read(name)
            if name == "project.json":
                meta = json.loads(data)
                meta["version"] = 1
                for b, shadow in zip(meta["blocks"][:3], (False, True, False)):
                    del b["font"]
                    b["shadow"] = shadow
                meta["blocks"][1]["is_reply"] = meta["blocks"][2]["is_reply"] = False
                data = json.dumps(meta).encode()
            zout.writestr(name, data)
    restored = project.load(dst, typography)
    assert [b.font for b in restored.blocks[:3]] == ["PeanutsRusbyme-Regular", "MPMangaFontBold",
                                                     "MPMangaFontBold-Bold"]


@pytest.mark.parametrize("content", [b"not a zip", b""])
def test_broken_file_is_reported(typography, tmp_path, content):
    path = tmp_path / "broken.rpeanuts"
    path.write_bytes(content)
    with pytest.raises(project.ProjectError):
        project.load(path, typography)


def test_foreign_or_newer_project_is_rejected(edited, typography, tmp_path):
    for patch, message in (({"format": "something-else"}, "не проект"), ({"version": 99}, "новой версией")):
        src, dst = tmp_path / "ok.rpeanuts", tmp_path / "patched.rpeanuts"
        project.save(edited, src)
        with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
            for name in zin.namelist():
                data = zin.read(name)
                if name == "project.json":
                    meta = json.loads(data)
                    meta.update(patch)
                    data = json.dumps(meta).encode()
                zout.writestr(name, data)
        with pytest.raises(project.ProjectError, match=message):
            project.load(dst, typography)


# --------------------------------------------------------------- окно

def test_window_saves_and_opens_project(typesetter, tmp_path, monkeypatch):
    from conftest import Typesetter
    from rus_peanuts.ui import main_window

    ts = typesetter.load_image(fixture_path("strips", "pe1963-04-08.png")).load_txt(DATA / "pe1963-04-08.txt")
    ts.select(ts.items[1])
    ts.win.spin_bold.setValue(2)
    path = tmp_path / "проект.rpeanuts"
    monkeypatch.setattr(main_window.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(path), "")))
    ts.win.act_save_project.trigger()
    assert path.exists()

    other = Typesetter(ts.win.typography)
    other.win.load_project(str(path))
    assert other.snapshot() == ts.snapshot()
    assert other.win.lbl_status.text().startswith("Проект открыт: проект.rpeanuts")
    assert other.win.current_txt_path is None
    other.win.close()


def test_window_reports_broken_project(typesetter, tmp_path, monkeypatch):
    from rus_peanuts.ui import main_window

    errors = []
    monkeypatch.setattr(main_window.QMessageBox, "critical", staticmethod(lambda *a, **k: errors.append(a)))
    bad = tmp_path / "bad.rpeanuts"
    bad.write_bytes(b"nope")
    typesetter.win.load_project(str(bad))
    assert len(errors) == 1
