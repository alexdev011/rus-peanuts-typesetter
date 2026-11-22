"""Датировка стрипов и Лист проверки."""
import datetime
import os

VALIDATION_LIST = "validation list.txt"


def next_day(date: str) -> str:
    """'1963-12-31' -> '1964-01-01'. Неверная дата — ValueError."""
    year, month, day = (int(p) for p in date.split("-"))
    return (datetime.date(year, month, day) + datetime.timedelta(days=1)).isoformat()


def date_from_name(file_name: str):
    """Дата стрипа из имени файла 'peYYYY-MM-DD.png' или 'YYYY-MM-DD.png', иначе None."""
    stem = file_name[:-4]
    if stem[:1].isdigit() and len(stem) == 10:
        return stem
    if len(stem) == 12:
        return stem[2:]
    return None


def add_to_validation_list(date: str, list_path: str = VALIDATION_LIST) -> None:
    dates = read_validation_list(list_path) if os.path.exists(list_path) else set()
    dates.add(date)
    with open(list_path, "w", encoding="utf-8") as f:
        f.write(", ".join(sorted(dates)))


def read_validation_list(list_path: str = VALIDATION_LIST) -> set:
    with open(list_path, "r", encoding="utf-8") as f:
        return {x.strip() for x in f.read().strip().split(",") if x.strip()}


def date_for_validation(file_name: str) -> str:
    """Дата для проверки: первые 10 символов, если имя начинается с цифры, иначе с 3-го по 12-й."""
    return file_name[0:10] if file_name[:1].isdigit() else file_name[2:12]
