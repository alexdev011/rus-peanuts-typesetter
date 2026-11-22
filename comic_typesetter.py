"""RUS PEANUTS — Auto-Typesetter & Multi-Tool.

Точка входа: `python comic_typesetter.py` (и для сборки PyInstaller).
Сам код живёт в пакете rus_peanuts/.
"""
from rus_peanuts.bootstrap import ensure_dependencies

ensure_dependencies()

from rus_peanuts.app import main  # noqa: E402 — только после проверки зависимостей

if __name__ == "__main__":
    main()
