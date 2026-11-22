"""Копирует образцы стрипов и страниц в tests/fixtures/ (папка в .gitignore).

Образцы защищены авторским правом, поэтому в репозиторий не попадают:
каждый разработчик собирает их у себя из архива команды.

    python tests/fetch_fixtures.py [путь_к_папке_Peanuts]

По умолчанию берётся C:/Users/<user>/Desktop/Peanuts.
Перевод для pe1963-04-13 вытаскивается из текстовых слоёв PSD команды.
"""
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

# Ежедневные стрипы (англ. оригинал) + один воскресный
STRIPS = [f"pe1963-04-{d:02d}.png" for d in range(8, 15)]
# Страницы сборника: две с тремя ежедневными стрипами, одна воскресная
PAGES = {
    "page_100.png": "page_100.png",
    "page_102.png": "page_102.png",
    "page_101.png": "wpage_101.png",  # 'w' в начале имени = воскресная Страница
    "page_103.png": "page_103.png",    # два соседних Бабла, которые нельзя склеивать
    "page_72.png": "page_72.png",
}
PSD_TRANSLATION = "pe1963-04-13"

SOUND_FONTS = ("MPManga",)


def translation_from_psd(psd_path: Path) -> str:
    from psd_tools import PSDImage

    psd = PSDImage.open(psd_path)
    lines = []
    for layer in psd.descendants():
        if layer.kind != "type":
            continue
        text = " ".join(layer.text.replace("\r", " ").split())
        fonts = [str(f["Name"]) for f in layer.resource_dict["FontSet"]]
        is_sound = any(s in fonts[0] for s in SOUND_FONTS)
        x1, y1, _, _ = layer.bbox
        lines.append((x1, y1, text if is_sound else f"- {text}"))
    lines.sort(key=lambda t: (t[0], t[1]))
    return "\n".join(t[2] for t in lines) + "\n"


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Desktop" / "Peanuts"
    strips_src = src / "Перевод" / "В переводе"
    pages_src = src / "Не переведеный 1963"

    (FIXTURES / "strips").mkdir(parents=True, exist_ok=True)
    (FIXTURES / "pages").mkdir(parents=True, exist_ok=True)
    (FIXTURES / "translations").mkdir(parents=True, exist_ok=True)

    for name in STRIPS:
        shutil.copy2(strips_src / name, FIXTURES / "strips" / name)
    for name, target in PAGES.items():
        shutil.copy2(pages_src / name, FIXTURES / "pages" / target)

    txt = translation_from_psd(strips_src / f"{PSD_TRANSLATION}.psd")
    (FIXTURES / "translations" / f"{PSD_TRANSLATION}.txt").write_text(txt, encoding="utf-8")

    print(f"Готово: {FIXTURES}")
    for p in sorted(FIXTURES.rglob("*")):
        if p.is_file():
            print("  ", p.relative_to(FIXTURES))


if __name__ == "__main__":
    os.chdir(HERE.parent)
    main()
