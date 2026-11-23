"""Совместимость Qt 6 (обычная сборка) и Qt 5 (сборка для Windows 8.1, см. requirements-legacy.txt).

Код пишется под PyQt6 через прослойку qtpy; здесь собрано то немногое, где Qt 5 ведёт себя иначе.
"""
from qtpy import QT5
from qtpy.QtCore import QCoreApplication, Qt
from qtpy.QtGui import QGuiApplication, QKeySequence


def prepare_qt() -> None:
    """Вызывать до создания QApplication.

    Вёрстка переводит кегль в пиксели стрипа по логическому DPI экрана (layout.Typography.set_text).
    Qt 6 на Windows всегда даёт 96 dpi, а масштаб экрана (125%, 150%) уносит в devicePixelRatio.
    Qt 5 по умолчанию отдаёт масштаб в DPI (120 dpi при 125%) — буквы вышли бы крупнее,
    и одна и та же Пачка сверсталась бы по-разному в двух сборках. PassThrough включает поведение Qt 6.
    """
    if not QT5:
        return
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)


def add_action(menu, text, slot, shortcut=None):
    """menu.addAction с горячей клавишей: в Qt 6 и Qt 5 порядок аргументов разный, поэтому клавиша — отдельно."""
    action = menu.addAction(text, slot)
    if shortcut:
        action.setShortcut(QKeySequence(shortcut))
    return action
