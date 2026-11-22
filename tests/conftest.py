"""Общая обвязка характеризационных тестов.

Тесты зафиксировали поведение монолита comic_typesetter.py до рефакторинга;
теперь они проверяют, что пакет rus_peanuts ведёт себя так же. Всё, что зависит
от формы кода (как создать окно, как вызвать операцию Multi tool), спрятано
в адаптеры этого файла.

Эталоны:
  * tests/golden/*.json — числа и хэши, коммитятся;
  * tests/fixtures/golden/*.png — эталонные картинки, только локально
    (производные от защищённых стрипов), нужны для разбора расхождений.
Обновить эталоны: UPDATE_GOLDEN=1 pytest
"""
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
FIXTURES = TESTS / "fixtures"
GOLDEN_JSON = TESTS / "golden"
GOLDEN_IMG = FIXTURES / "golden"
ACTUAL_IMG = FIXTURES / "_actual"
UPDATE = os.environ.get("UPDATE_GOLDEN") == "1"

sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------- приложение

@pytest.fixture(scope="session")
def qt_app():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="session")
def typography(qt_app):
    """Typography с настоящими шрифтами проекта (ищутся в ./fonts)."""
    from rus_peanuts.typesetting.fonts import load_fonts
    from rus_peanuts.typesetting.layout import Typography

    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        return Typography(load_fonts())
    finally:
        os.chdir(cwd)


@pytest.fixture
def doc(typography):
    from rus_peanuts.typesetting.document import Document

    return Document(typography)


def block_state(b):
    """Состояние TextBlock в виде, в котором оно лежит в эталонах."""
    return {
        "text": b.text,
        "is_bubble": b.is_reply,
        "is_outlined": b.shadow,
        "x": round(b.x, 2),
        "y": round(b.y, 2),
        "size": round(b.size, 2),
        "width": round(b.width, 2),
        "stretch": b.stretch,
        "italic": b.italic,
        "bold": b.bold,
        "arch": b.arch,
    }


def fixture_path(*parts) -> Path:
    p = FIXTURES.joinpath(*parts)
    if not p.exists():
        pytest.skip(f"нет образца {p.relative_to(TESTS)} — запусти tests/fetch_fixtures.py")
    return p


# ------------------------------------------------------------------- эталоны

def image_digest(img) -> str:
    import numpy as np

    arr = np.ascontiguousarray(img)
    h = hashlib.sha256()
    h.update(str((arr.shape, str(arr.dtype))).encode())
    h.update(arr.tobytes())
    return h.hexdigest()[:16]


class Golden:
    def __init__(self, name: str):
        self.name = name
        self.path = GOLDEN_JSON / f"{name}.json"

    def check(self, data):
        """Сравнивает JSON-сериализуемые данные с эталоном."""
        data = json.loads(json.dumps(data, ensure_ascii=False))
        if UPDATE or not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            if not UPDATE:
                pytest.skip(f"создан эталон {self.path.name}, перезапусти тесты")
            return
        expected = json.loads(self.path.read_text(encoding="utf-8"))
        assert data == expected

    def image(self, key: str, img) -> str:
        """Сохраняет картинку как локальный эталон и возвращает её хэш для JSON."""
        import cv2

        digest = image_digest(img)
        name = f"{self.name}__{key}.png"
        golden_png = GOLDEN_IMG / name
        if UPDATE or not golden_png.exists():
            GOLDEN_IMG.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(golden_png), img)
        else:
            ref = cv2.imread(str(golden_png), cv2.IMREAD_UNCHANGED)
            if ref is None or image_digest(ref) != digest:
                ACTUAL_IMG.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(ACTUAL_IMG / name), img)
        return digest


@pytest.fixture
def golden(request):
    def make(suffix: str = "") -> Golden:
        base = request.node.name.replace("[", "__").replace("]", "").replace("/", "_")
        return Golden(base + (f"__{suffix}" if suffix else ""))

    return make


# ------------------------------------------------- адаптер: окно вёрстки

class Typesetter:
    """Тонкая обёртка над MainWindow: единственное место, которое знает про его поля."""

    def __init__(self, typography):
        from rus_peanuts.ui.main_window import MainWindow

        self.win = MainWindow(typography)

    def load_image(self, path):
        self.win.load_image(str(path))
        return self

    def load_txt(self, path):
        self.win.load_txt(str(path))
        return self

    @property
    def doc(self):
        return self.win.document

    @property
    def items(self):
        return list(self.win.items)

    def snapshot(self):
        return [block_state(b) for b in self.doc.blocks]

    def select(self, *items):
        self.win.scene.clearSelection()
        for it in items:
            it.setSelected(True)

    def render(self, out_path, monkeypatch):
        """Сохраняет результат через настоящую кнопку «Сохранить (PNG)»."""
        import cv2
        from rus_peanuts.ui import main_window

        monkeypatch.setattr(main_window.QFileDialog, "getSaveFileName",
                            staticmethod(lambda *a, **k: (str(out_path), "")))
        monkeypatch.setattr(main_window.QMessageBox, "information", staticmethod(lambda *a, **k: None))
        self.win.save_result()
        return cv2.imread(str(out_path), cv2.IMREAD_UNCHANGED)


@pytest.fixture
def typesetter(typography):
    ts = Typesetter(typography)
    yield ts
    ts.win.close()
    ts.win.deleteLater()


# --------------------------------------------------- адаптер: Multi tool

class MultiTool:
    """Запускает операции Multi tool так же, как кнопка «Go» во вкладке Qt."""

    def __init__(self, workdir: Path):
        self.workdir = workdir
        self.logs = []

    def run(self, path, operation, folder=False, contrast=False, date="YYYY-MM-DD"):
        from rus_peanuts import publishing

        publishing.run(str(path).replace("\\", "/"), operation, folder=folder,
                       contrast=contrast, date=date, log=self.logs.append)
        return self

    def results(self):
        """Имена и картинки из папки result/ (как их прочитал бы человек)."""
        import cv2
        import numpy as np

        out = {}
        res = self.workdir / "result"
        if res.exists():
            for p in sorted(res.iterdir()):
                out[p.name] = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        return out


@pytest.fixture
def multitool(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # Multi tool пишет result/ и 'validation list.txt' в текущую папку
    return MultiTool(tmp_path)


@pytest.fixture(autouse=True)
def no_modal_dialogs(monkeypatch):
    """Страховка: модальное окно в тесте ждало бы клика вечно. Тест может переопределить."""
    from PyQt6.QtWidgets import QFileDialog, QMessageBox

    for name in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: None))
    for name in ("getSaveFileName", "getOpenFileName"):
        monkeypatch.setattr(QFileDialog, name, staticmethod(lambda *a, **k: ("", "")))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ""))
