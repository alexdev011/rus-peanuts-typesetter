"""Подготовка стрипов к публикации (бывший Multi tool).

Единственная точка входа для интерфейса — `run()`.
"""
import os

from . import dating, pages
from .raster import Picture, load, save

RESULT_DIR = "result"
IMAGE_SUFFIXES = ("jpg", "png", "gif")

# операция -> подпись в интерфейсе
OPERATIONS = {
    "slice": "Slice",
    "date": "Date",
    "square": "Square",
    "acomics": "acomics",
    "add_to_validation_list": "add to validation list",
    "validate": "validate",
    "nothing": "Nothing",
}

# Временно скрыты из интерфейса по просьбе команды; код и тесты остаются,
# чтобы вернуть операцию, достаточно убрать её отсюда.
HIDDEN_OPERATIONS = {"acomics", "add_to_validation_list", "validate"}


def visible_operations() -> dict:
    """Операции, которые показываются во вкладке, в порядке показа."""
    return {op: title for op, title in OPERATIONS.items() if op not in HIDDEN_OPERATIONS}


_NEEDS_PIXELS = {"slice", "date", "square", "acomics", "nothing"}


def run(path: str, operation: str, *, folder: bool, contrast: bool, date: str, log,
        result_dir: str = RESULT_DIR) -> None:
    """Выполняет операцию над файлом или над всеми картинками папки.

    Результаты пишутся в `result_dir`, сообщения — через `log(str)`.
    Ошибка не выбрасывается наружу: она уходит в лог и прерывает пачку.
    Если путь начинается с цифры, он считается датой стрипа (для «validate»).
    """
    os.makedirs(result_dir, exist_ok=True)
    job = _Job(operation, contrast, date, log, result_dir)
    try:
        if path[:1].isdigit():
            job.process(path, None)
        elif folder:
            for name in sorted(os.listdir(path)):
                if name.endswith(IMAGE_SUFFIXES):
                    job.process(name, path + "/" + name)
        else:
            job.process(path.split("/")[-1], path)
    except Exception as e:  # noqa: BLE001 — так было в Multi tool: всё в лог
        log(str(e))


class _Job:
    def __init__(self, operation, contrast, date, log, result_dir):
        self.operation = operation
        self.contrast = contrast
        self.date = date  # меняется по ходу Датировки
        self.log = log
        self.result_dir = result_dir

    def process(self, file_name: str, file_path):
        picture = None
        if self.operation in _NEEDS_PIXELS:
            if file_path is None:
                raise ValueError(f"«{file_name}» — не картинка")
            picture = load(file_path)
            if self.contrast:
                picture = pages.contrast(picture)

        op = self.operation
        if op == "slice":
            if file_name[:1] == "w":
                self._save(pages.slice_sunday_page(picture), file_name)
            else:
                for i, strip in enumerate(pages.slice_daily_page(picture)):
                    self._save(strip, file_name, index=i)
        elif op == "date":
            self._save(picture, "pe" + self.date + ".png")
            self.date = dating.next_day(self.date)
        elif op == "square":
            self._save(pages.square(picture), file_name)
        elif op == "acomics":
            self._save(pages.fit_acomics(picture), file_name)
        elif op == "add_to_validation_list":
            strip_date = dating.date_from_name(file_name)
            if strip_date is None:
                self.log(
                    f'Стрип не правльно назван или \nне правильного формата, его название\n'
                    f'{file_name[:-4]}.\nСтрип должен быть peYYYY-MM-DD.png или\nYYYY-MM-DD.png. Обязательно пнг'
                )
                return
            dating.add_to_validation_list(strip_date)
            self.log(f"Стрип по дате: {strip_date} добавлен в лист")
        elif op == "validate":
            strip_date = dating.date_for_validation(file_name)
            if strip_date in dating.read_validation_list():
                self.log(f"Стрип по дате: {strip_date} уже переведен")
            else:
                self.log(f"Стрип по дате: {strip_date} не переведен")
        else:
            self._save(picture, file_name)

    def _save(self, picture: Picture, file_name: str, index=None):
        stem = file_name[:-4] + (f" {index}" if index is not None else "")
        save(picture, os.path.join(self.result_dir, stem + ".png"))
