"""Проверка зависимостей до импорта PyQt/OpenCV (поэтому здесь только стандартная библиотека)."""
import subprocess
import sys


def ensure_dependencies():
    """Проверяет наличие нужных библиотек перед запуском и автоматически докачивает их (либо выводит удобное окно)"""
    if getattr(sys, "frozen", False):
        return

    required = [
        ("qtpy", "QtPy"),
        ("cv2", "opencv-python"),
        ("numpy", "numpy"),
        ("PIL", "Pillow"),
    ]
    missing = []
    for mod_name, pip_name in required:
        try:
            __import__(mod_name)
        except ImportError:
            missing.append(pip_name)
    # qtpy — только прослойка: нужна сама Qt. Годится PyQt6 (обычная сборка)
    # или PyQt5 (сборка для Windows 8.1, см. requirements-legacy.txt).
    if not any(_importable(binding) for binding in ("PyQt6", "PyQt5")):
        missing.append("PyQt6")

    if not missing:
        return

    missing_str = ", ".join(missing)
    print(f"[!] Не хватает библиотек для запуска: {missing_str}")
    print("[*] Пробуем автоматически установить их через pip...")

    should_install = True
    try:
        import ctypes
        msg = (
            f"Для работы программы не хватает следующих библиотек:\n"
            f"• {missing_str}\n\n"
            f"Нажми «Да», чтобы программа сама скачала и установила их сейчас автоматически!\n"
            f"(Или «Нет», если хочешь установить вручную командой: pip install {' '.join(missing)})"
        )
        # MB_YESNO | MB_ICONQUESTION = 0x04 | 0x20 = 0x24; IDYES = 6
        res = ctypes.windll.user32.MessageBoxW(0, msg, "RUS PEANUTS — Установка библиотек", 0x24)
        if res != 6:
            should_install = False
    except Exception:
        pass

    if not should_install:
        sys.exit(1)

    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
        print("[+] Все библиотеки успешно установлены! Запускаем программу...")
    except Exception as e:
        err_msg = (
            f"Не удалось автоматически установить библиотеки: {missing_str}\n\n"
            f"Ошибка: {e}\n\n"
            f"Открой командную строку (cmd) и выполни команду вручную:\n"
            f"pip install {' '.join(missing)}"
        )
        print(err_msg)
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, err_msg, "Ошибка установки библиотек", 0x10)
        except Exception:
            pass
        sys.exit(1)


def _importable(mod_name: str) -> bool:
    try:
        __import__(mod_name)
    except ImportError:
        return False
    return True
