"""Пачка: Оригиналы из одной папки и один Файл перевода.

Стрипы верстаются по очереди. Оригинал находит свой Перевод по Дате стрипа в имени
файла (`pe1963-04-08.png` -> `1963-04-08`). Документ стрипа создаётся при первом
открытии. Пока стрип не правили, его Документ не хранится: при следующем открытии он
собирается заново и подхватывает изменения Файла перевода. Исправленные руками стрипы
помнятся до закрытия программы.
"""
import re
from dataclasses import dataclass
from pathlib import Path

from rus_peanuts.export.png import export_png

from . import analysis, project, translation
from .document import Document

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")
_DATE_IN_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})")


def strip_date(path) -> str | None:
    """Дата стрипа из имени файла (`pe1963-04-08.png`, `1963-04-08 копия.jpg`), иначе None."""
    m = _DATE_IN_NAME.search(Path(path).stem)
    return m.group(1) if m else None


@dataclass
class Strip:
    """Стрип Пачки."""
    path: Path
    date: str | None
    document: Document | None = None
    saved: bool = False         # сохранён «Сохранить все» или командой сохранения

    @property
    def name(self) -> str:
        return self.path.stem

    @property
    def unsaved(self) -> bool:
        return self.document is not None and self.document.dirty


@dataclass(frozen=True)
class Problems:
    """Что в Пачке не сходится с Файлом перевода."""
    no_date: list           # имена стрипов без даты в имени файла
    no_translation: list    # имена стрипов, для чьей даты нет Перевода
    no_strip: list          # даты Переводов, для которых нет стрипа
    duplicates: list        # даты, которые в Файле перевода встречаются не один раз

    def __bool__(self) -> bool:
        return bool(self.no_date or self.no_translation or self.no_strip or self.duplicates)


class Batch:
    def __init__(self, folder, typography, translation_path=None):
        self.folder = Path(folder)
        self.typography = typography
        self.translation_path = translation_path
        self.strips = [Strip(p, strip_date(p)) for p in sorted(self.folder.iterdir(), key=lambda p: p.name.lower())
                       if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]

    # -------------------------------------------------------------- Перевод

    def translation(self) -> translation.TranslationFile | None:
        """Файл перевода, прочитанный с диска заново (его могли поправить)."""
        return translation.read(self.translation_path) if self.translation_path else None

    def lines_for(self, strip: Strip, tf=None) -> list | None:
        tf = tf if tf is not None else self.translation()
        if tf is None or strip.date is None:
            return None
        return tf.for_date(strip.date)

    def set_translation(self, path) -> None:
        """Новый Файл перевода. Нетронутые стрипы соберутся с ним заново при открытии."""
        self.translation_path = path
        for strip in self.strips:
            if strip.document is not None and not strip.document.edited:
                strip.document = None

    def problems(self) -> Problems:
        tf = self.translation()
        dates = {s.date for s in self.strips if s.date}
        return Problems(
            no_date=[s.name for s in self.strips if s.date is None],
            no_translation=[s.name for s in self.strips if s.date and (tf is None or tf.for_date(s.date) is None)],
            no_strip=[d for d in (tf.dates if tf else []) if d not in dates],
            duplicates=list(tf.duplicates) if tf else [],
        )

    # ---------------------------------------------------------------- стрипы

    def open(self, index: int) -> Document:
        """Документ стрипа: уже исправленный — как есть, иначе собирается заново."""
        strip = self.strips[index]
        if strip.document is None:
            image = analysis.load_image(strip.path)
            if image is None:
                raise OSError(f"не удалось открыть {strip.path.name}")
            doc = Document(self.typography)
            doc.open_strip(image, self.lines_for(strip) or [])
            strip.document = doc
        return strip.document

    def leave(self, index: int) -> None:
        """Уйти со стрипа: если его не правили, Документ не держим в памяти."""
        strip = self.strips[index]
        if strip.document is not None and not strip.document.edited:
            strip.document = None

    def unsaved(self) -> list[Strip]:
        return [s for s in self.strips if s.unsaved]

    def save_all(self, out_dir, log=lambda message: None) -> list[str]:
        """PNG и файл проекта для каждого стрипа. Возвращает ошибки (пусто — всё сохранено)."""
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        errors = []
        for k, strip in enumerate(self.strips):
            log(f"Сохраняю {k + 1} из {len(self.strips)}: {strip.name}")
            try:
                keep = strip.document is not None
                doc = self.open(k)
                if not export_png(doc, self.typography, out / f"{strip.name}.png"):
                    raise OSError("PNG не записался")
                project.save(doc, out / f"{strip.name}{project.EXTENSION}")
                doc.mark_saved()
                strip.saved = True
                if not keep:
                    self.leave(k)
            except (OSError, project.ProjectError) as e:
                errors.append(f"{strip.name}: {e}")
        return errors
