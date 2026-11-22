import sys
import os
import re
import copy
import base64
import subprocess
import math
import struct


def ensure_dependencies():
    """Проверяет наличие нужных библиотек перед запуском и автоматически докачивает их (либо выводит удобное окно)"""
    if getattr(sys, "frozen", False):
        return

    required = [
        ("PyQt6", "PyQt6"),
        ("cv2", "opencv-python"),
        ("numpy", "numpy"),
        ("wand", "Wand"),
        ("PIL", "Pillow"),
    ]
    missing = []
    for mod_name, pip_name in required:
        try:
            __import__(mod_name)
        except ImportError:
            missing.append(pip_name)

    if not missing:
        return

    missing_str = ", ".join(missing)
    cmd_str = f"{sys.executable} -m pip install {' '.join(missing)}"
    print(f"[!] Не хватает библиотек для запуска: {missing_str}")
    print(f"[*] Пробуем автоматически установить их через pip...")

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



def ensure_imagemagick_engine():
    import glob
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    candidate_dirs = [
        os.path.join(exe_dir, "imagemagick"),
        os.path.join(exe_dir, "ImageMagick"),
    ]
    if hasattr(sys, "_MEIPASS"):
        candidate_dirs.insert(0, os.path.join(sys._MEIPASS, "imagemagick"))

    for pf_env in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData"):
        pf_path = os.environ.get(pf_env)
        if pf_path:
            candidate_dirs.extend(glob.glob(os.path.join(pf_path, "ImageMagick*")))

    for d in candidate_dirs:
        if os.path.isdir(d):
            dlls = glob.glob(os.path.join(d, "*MagickWand*.dll")) + glob.glob(os.path.join(d, "CORE_RL_wand*.dll"))
            if dlls:
                os.environ["MAGICK_HOME"] = d
                if d not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
                break

    try:
        from wand.image import Image as _TestWandImage
        return True
    except ImportError as e:
        print(f"[!] Системный движок ImageMagick не найден: {e}")

    if os.name == "nt":
        should_install_im = True
        try:
            import ctypes
            msg = (
                "Для работы второй вкладки («Multi tool for Pinats») требуется системная программа ImageMagick (DLL), "
                "которая сейчас не установлена на этом компьютере.\n\n"
                "Нажми «Да», чтобы скачать и установить ImageMagick автоматически прямо сейчас!\n"
                "(После установки нужно будет один раз перезапустить программу)."
            )
            res = ctypes.windll.user32.MessageBoxW(0, msg, "Автоустановка ImageMagick", 0x24)
            if res != 6:
                should_install_im = False
        except Exception:
            pass

        if should_install_im:
            installed_ok = False
            try:
                print("[*] Пробуем установить ImageMagick через winget...")
                ret = subprocess.call([
                    "winget", "install", "--id", "ImageMagick.ImageMagick",
                    "-e", "--accept-source-agreements", "--accept-package-agreements"
                ])
                if ret == 0:
                    installed_ok = True
            except Exception:
                pass

            if not installed_ok:
                try:
                    import urllib.request
                    import tempfile
                    print("[*] Скачиваем официальный установщик ImageMagick...")
                    html = urllib.request.urlopen("https://imagemagick.org/archive/binaries/", timeout=15).read().decode("utf-8", errors="ignore")
                    matches = re.findall(r'(ImageMagick-7\.[0-9.\-]+-Q16-HDRI-x64-dll\.exe)', html)
                    if matches:
                        installer_name = sorted(set(matches))[-1]
                        url = f"https://imagemagick.org/archive/binaries/{installer_name}"
                        tmp_exe = os.path.join(tempfile.gettempdir(), installer_name)
                        urllib.request.urlretrieve(url, tmp_exe)
                        print(f"[*] Запускаем установку {installer_name}...")
                        subprocess.check_call([tmp_exe, "/SILENT", "/NORESTART"])
                        installed_ok = True
                except Exception as ex:
                    print(f"[!] Не удалось автоматически скачать установщик: {ex}")

            for pf_env in ("ProgramFiles", "ProgramFiles(x86)"):
                pf_path = os.environ.get(pf_env)
                if pf_path:
                    for d in glob.glob(os.path.join(pf_path, "ImageMagick*")):
                        if os.path.isdir(d):
                            os.environ["MAGICK_HOME"] = d
                            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            try:
                from wand.image import Image as _TestWandImage
                return True
            except ImportError:
                if installed_ok:
                    try:
                        import ctypes
                        ctypes.windll.user32.MessageBoxW(0, "ImageMagick успешно установлен! Перезапусти программу.", "ImageMagick установлен", 0x40)
                    except Exception:
                        pass
    return False

HAS_IMAGEMAGICK = ensure_imagemagick_engine()
ensure_dependencies()


import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QGraphicsView, QGraphicsScene,
    QGraphicsTextItem, QGraphicsPixmapItem, QLabel, QMessageBox,
    QStyleOptionGraphicsItem, QStyle, QDialog, QSlider
)
from PyQt6.QtGui import (
    QPixmap, QImage, QColor, QFont, QFontDatabase, 
    QBrush, QPen, QPainter, QFontMetrics, QIcon, QKeySequence, QShortcut,
    QTextCharFormat, QTextCursor, QPainterPath
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QByteArray

FONTS = {"peanuts": "Comic Sans MS", "manga": "Arial Black", "manga_shadow": "Arial Black"}
FONT_STYLES = {"peanuts": "", "manga": "", "manga_shadow": ""}

# Вшитые изображения
EMBEDDED_APP_ICON_B64 = "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"
EMBEDDED_LOGO_B64 = "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"
EMBEDDED_GUIDE_IMG_B64 = "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"
EMBEDDED_ABOUT_IMG_B64 = "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"


def load_b64_pixmap(b64_str):
    raw_bytes = QByteArray.fromBase64(b64_str.encode("ascii"))
    pix = QPixmap()
    pix.loadFromData(raw_bytes, "PNG")
    return pix


def get_resource_path(rel_path):
    """Находит файлы как внутри собранного .exe (PyInstaller _MEIPASS), так и рядом с .exe/.py"""
    if hasattr(sys, "_MEIPASS"):
        bundled = os.path.join(sys._MEIPASS, rel_path)
        if os.path.exists(bundled):
            return bundled
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    near_exe = os.path.join(exe_dir, rel_path)
    if os.path.exists(near_exe):
        return near_exe
    return rel_path


def rename_ttf_family(ttf_bytes: bytes, new_family: str) -> bytes:
    """Переименовывает family/subfamily в таблице 'name' TTF-файла в памяти, чтобы Qt никогда не путал Shadow и обычный Bold."""
    if len(ttf_bytes) < 12:
        return ttf_bytes
    sfnt_version, num_tables, search_range, entry_selector, range_shift = struct.unpack(">IHHHH", ttf_bytes[:12])
    if sfnt_version not in (0x00010000, 0x4F54544F):
        return ttf_bytes

    tables = {}
    table_order = []
    pos = 12
    for _ in range(num_tables):
        tag = ttf_bytes[pos:pos+4].decode("latin1")
        checksum, offset, length = struct.unpack(">III", ttf_bytes[pos+4:pos+16])
        tables[tag] = ttf_bytes[offset:offset+length]
        table_order.append(tag)
        pos += 16

    if "name" not in tables:
        return ttf_bytes

    ps_name = "".join(ch for ch in new_family if ch.isalnum() or ch in "-_")
    entries_spec = [
        (1, new_family),
        (2, "Regular"),
        (4, new_family),
        (6, ps_name),
        (16, new_family),
        (17, "Regular"),
    ]

    records = []
    str_data = bytearray()
    for nid, text in entries_spec:
        enc = text.encode("ascii", errors="ignore")
        records.append((1, 0, 0, nid, len(enc), len(str_data)))
        str_data.extend(enc)
    for nid, text in entries_spec:
        enc = text.encode("utf-16-be")
        records.append((3, 1, 0x0409, nid, len(enc), len(str_data)))
        str_data.extend(enc)

    records.sort(key=lambda r: (r[0], r[1], r[2], r[3]))
    string_offset = 6 + len(records) * 12
    new_name = bytearray(struct.pack(">HHH", 0, len(records), string_offset))
    for r in records:
        new_name.extend(struct.pack(">HHHHHH", *r))
    new_name.extend(str_data)
    tables["name"] = bytes(new_name)

    def calc_checksum(data: bytes) -> int:
        pad = (4 - (len(data) % 4)) % 4
        padded = data + b"\x00" * pad
        total = 0
        for i in range(0, len(padded), 4):
            total = (total + struct.unpack(">I", padded[i:i+4])[0]) & 0xFFFFFFFF
        return total

    if "head" in tables and len(tables["head"]) >= 12:
        head_ba = bytearray(tables["head"])
        head_ba[8:12] = b"\x00\x00\x00\x00"
        tables["head"] = bytes(head_ba)

    out = bytearray(struct.pack(">IHHHH", sfnt_version, num_tables, search_range, entry_selector, range_shift))
    dir_pos = len(out)
    out.extend(b"\x00" * (num_tables * 16))

    head_file_offset = None
    for idx, tag in enumerate(table_order):
        data = tables[tag]
        offset = len(out)
        if tag == "head":
            head_file_offset = offset
        csum = calc_checksum(data)
        entry = tag.encode("latin1") + struct.pack(">III", csum, offset, len(data))
        out[dir_pos + idx*16 : dir_pos + (idx+1)*16] = entry
        out.extend(data)
        pad = (4 - (len(data) % 4)) % 4
        if pad:
            out.extend(b"\x00" * pad)

    if head_file_offset is not None:
        whole_csum = calc_checksum(bytes(out))
        adj = (0xB1B0AFBA - whole_csum) & 0xFFFFFFFF
        out[head_file_offset + 8 : head_file_offset + 12] = struct.pack(">I", adj)

    return bytes(out)


def init_fonts():
    """Сканирует папки проекта и системные папки шрифтов Windows, изолирует имена manga и manga_shadow в памяти."""
    dirs_to_scan = []
    if hasattr(sys, "_MEIPASS"):
        dirs_to_scan.append(os.path.join(sys._MEIPASS, "fonts"))
        dirs_to_scan.append(sys._MEIPASS)
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    dirs_to_scan.extend([
        os.path.join(exe_dir, "fonts"),
        exe_dir,
        os.path.abspath("fonts"),
        os.path.abspath("."),
    ])
    # проверка системных папок шрифтов Windows
    if os.name == "nt":
        local_app = os.environ.get("LOCALAPPDATA", "")
        win_dir = os.environ.get("WINDIR", "C:\\Windows")
        if local_app:
            dirs_to_scan.append(os.path.join(local_app, "Microsoft", "Windows", "Fonts"))
        dirs_to_scan.append(os.path.join(win_dir, "Fonts"))

    seen_files = set()
    found_keys = set()

    unique_names = {
        "peanuts": "RusPeanuts_Dialogue",
        "manga": "RusPeanuts_MangaSolid",
        "manga_shadow": "RusPeanuts_MangaShadow",
    }

    def register_font_isolated(key, filepath):
        try:
            with open(filepath, "rb") as f:
                raw = f.read()
            patched = rename_ttf_family(raw, unique_names[key])
            fid = QFontDatabase.addApplicationFontFromData(QByteArray(patched))
            if fid != -1:
                fams = QFontDatabase.applicationFontFamilies(fid)
                if fams:
                    FONTS[key] = fams[0]
                    FONT_STYLES[key] = ""
                    found_keys.add(key)
                    return True
        except Exception:
            pass
        # запасной вариант
        fid = QFontDatabase.addApplicationFont(filepath)
        if fid != -1:
            fams = QFontDatabase.applicationFontFamilies(fid)
            if fams:
                FONTS[key] = fams[0]
                FONT_STYLES[key] = ""
                found_keys.add(key)
                return True
        return False

    font_files = []
    for d in dirs_to_scan:
        if os.path.isdir(d):
            try:
                for fname in sorted(os.listdir(d)):
                    low = fname.lower()
                    if low.endswith((".ttf", ".otf")):
                        full_p = os.path.normpath(os.path.join(d, fname))
                        if full_p not in seen_files:
                            seen_files.add(full_p)
                            font_files.append((low, full_p))
            except Exception:
                pass

    for low, full_p in font_files:
        if "peanuts" in low and "peanuts" not in found_keys:
            register_font_isolated("peanuts", full_p)

    for low, full_p in font_files:
        if "manga" in low and "shadow" not in low and "manga" not in found_keys:
            register_font_isolated("manga", full_p)

    for low, full_p in font_files:
        if "shadow" in low and ("manga" in low or "mp" in low) and "manga_shadow" not in found_keys:
            register_font_isolated("manga_shadow", full_p)

    # запасной поиск
    all_fams = QFontDatabase.families()
    if "peanuts" not in found_keys:
        for fam in all_fams:
            if "peanuts" in fam.lower():
                FONTS["peanuts"] = fam
                found_keys.add("peanuts")
                break
    if "manga" not in found_keys:
        for fam in all_fams:
            low = fam.lower()
            if "manga" in low and "shadow" not in low:
                FONTS["manga"] = fam
                found_keys.add("manga")
                break
    if "manga_shadow" not in found_keys:
        for fam in all_fams:
            low = fam.lower()
            if "shadow" in low and ("manga" in low or "mp" in low):
                FONTS["manga_shadow"] = fam
                found_keys.add("manga_shadow")
                break
        if "manga_shadow" not in found_keys:
            FONTS["manga_shadow"] = FONTS["manga"]


def hyphenate_russian_word(word):
    vowels = set("АЕЁИОУЫЭЮЯаеёиоуыэюя")
    if len(word) < 7:
        return word
    v_indices = [i for i, ch in enumerate(word) if ch in vowels]
    if len(v_indices) < 2:
        return word

    parts = []
    last_idx = 0
    for k in range(len(v_indices) - 1):
        v1 = v_indices[k]
        v2 = v_indices[k + 1]
        cut = v1 + 1 if (v2 - v1) <= 2 else v1 + 2
        while cut < v2 and word[cut] in "ЬЪЙьъй":
            cut += 1
        if cut >= 2 and (len(word) - cut) >= 2 and cut > last_idx:
            parts.append(word[last_idx:cut])
            last_idx = cut

    parts.append(word[last_idx:])
    return "\u00AD".join(parts)


def hyphenate_text(text):
    return re.sub(r"[А-ЯЁа-яё]{7,}", lambda m: hyphenate_russian_word(m.group(0)), text)


def analyze_strip_universal(image_path):
    """
    Оптимизированный универсальный анализатор (v7):
    Использует LUT-таблицы NumPy для мгновенного наложения масок, что сокращает время "думания" в 10-20 раз!
    """
    stream = np.fromfile(image_path, dtype=np.uint8)
    img = cv2.imdecode(stream, cv2.IMREAD_COLOR)
    if img is None:
        return None, None, [], []

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape

    _, dark_mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    _, white_mask = cv2.threshold(gray, 210, 255, cv2.THRESH_BINARY)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(dark_mask, connectivity=8)

    barrier_ids = []
    candidates = []
    sfx_candidates = []

    for i in range(1, num_labels):
        x, y, w, h, area = stats[i]

        if y < 28 and x < W * 0.35:
            barrier_ids.append(i)
            continue

        if 30 <= h <= min(140, int(H * 0.25)) and 4 <= w <= h * 1.6 and area >= 35:
            pad = 5
            y1, y2 = max(0, y - pad), min(H, y + h + pad)
            x1, x2 = max(0, x - pad), min(W, x + w + pad)
            if np.mean(white_mask[y1:y2, x1:x2]) > 135:
                sfx_candidates.append((i, x, y, w, h))

        if w > 48 or h > 45 or area > 800:
            barrier_ids.append(i)
            continue

        if 7 <= h <= 42 and 2 <= w <= h * 3.0 and area >= 8:
            pad = 4
            y1, y2 = max(0, y - pad), min(H, y + h + pad)
            x1, x2 = max(0, x - pad), min(W, x + w + pad)
            if np.mean(white_mask[y1:y2, x1:x2]) > 160:
                candidates.append((i, x, y, w, h))

    barrier_lut = np.zeros(num_labels, dtype=np.uint8)
    barrier_lut[barrier_ids] = 255
    barrier_mask = barrier_lut[labels]

    verified_letters = []
    verified_ids = []

    for (idx_i, x, y, w, h) in candidates:
        cy = y + h / 2.0
        neighbors = 0
        for (idx_j, nx, ny, nw, nh) in candidates:
            if idx_i == idx_j:
                continue
            ncy = ny + nh / 2.0
            if abs(cy - ncy) < h * 0.60 and abs(h - nh) <= max(4, h * 0.28):
                dist_x = max(0, max(x - (nx + nw), nx - (x + w)))
                if dist_x < h * 2.5:
                    mid_x = int(((x + w / 2) + (nx + nw / 2)) / 2)
                    mid_y = int((cy + ncy) / 2)
                    if barrier_mask[mid_y, mid_x] == 0:
                        neighbors += 1
        if neighbors >= 2:
            verified_letters.append((idx_i, x, y, w, h))
            verified_ids.append(idx_i)

    med_h = float(np.median([b[4] for b in verified_letters])) if verified_letters else 15.0

    filtered_letters = []
    filtered_ids = []
    for b in verified_letters:
        if med_h * 0.65 <= b[4] <= med_h * 1.45:
            filtered_letters.append(b)
            filtered_ids.append(b[0])

    filtered_lut = np.zeros(num_labels, dtype=np.uint8)
    filtered_lut[filtered_ids] = 255
    filtered_mask = filtered_lut[labels]

    near_filtered = cv2.dilate(filtered_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (int(med_h * 2.2), int(med_h * 0.8))))
    for (idx_i, x, y, w, h) in candidates:
        if med_h * 0.55 <= h <= med_h * 1.45 and np.any(near_filtered[y:y+h, x:x+w] > 0):
            if not np.any(barrier_mask[y:y+h, max(0, x-12):x+w] > 0):
                if (idx_i, x, y, w, h) not in filtered_letters:
                    filtered_letters.append((idx_i, x, y, w, h))
                    filtered_ids.append(idx_i)

    filtered_lut = np.zeros(num_labels, dtype=np.uint8)
    filtered_lut[filtered_ids] = 255
    filtered_mask = filtered_lut[labels]

    kw = max(16, int(med_h * 1.55))
    kh = max(11, int(med_h * 1.15))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kw, kh))
    grouped = cv2.dilate(filtered_mask, kernel, iterations=1)

    thick_barriers = cv2.dilate(barrier_mask, np.ones((3, 3), np.uint8), iterations=1)
    grouped[thick_barriers > 0] = 0

    contours, _ = cv2.findContours(grouped, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    valid_bubbles = []
    for cnt in contours:
        bx, by, bw, bh = cv2.boundingRect(cnt)
        in_box = [
            b for b in filtered_letters
            if bx <= b[1] and (b[1] + b[3]) <= (bx + bw) and by <= b[2] and (b[2] + b[4]) <= (by + bh)
        ]
        if len(in_box) < 6 or bw < med_h * 2.5:
            continue

        roi_white = white_mask[by:by+bh, bx:bx+bw]
        if np.mean(roi_white) < 170:
            continue

        min_x = min(b[1] for b in in_box)
        min_y = min(b[2] for b in in_box)
        max_x = max(b[1] + b[3] for b in in_box)
        max_y = max(b[2] + b[4] for b in in_box)

        pad_l, pad_r, pad_y = 6, 14, 5
        rx = max(0, min_x - pad_l)
        ry = max(0, min_y - pad_y)
        rw = min(W - rx, (max_x - min_x) + pad_l + pad_r)
        rh = min(H - ry, (max_y - min_y) + pad_y * 2)
        valid_bubbles.append((rx, ry, rw, rh))

    sfx_verified = []
    sfx_ids = []
    for (idx_i, x, y, w, h) in sfx_candidates:
        if y < H * 0.45 and x < W * 0.45:
            continue
        cy = y + h / 2.0
        neighbors = 0
        for (idx_j, nx, ny, nw, nh) in sfx_candidates:
            if idx_i == idx_j:
                continue
            ncy = ny + nh / 2.0
            if abs(cy - ncy) < h * 0.45 and abs(h - nh) <= h * 0.30:
                dist_x = max(0, max(x - (nx + nw), nx - (x + w)))
                if dist_x < h * 1.2:
                    neighbors += 1
        if neighbors >= 3:
            sfx_verified.append((idx_i, x, y, w, h))
            sfx_ids.append(idx_i)

    sfx_lut = np.zeros(num_labels, dtype=np.uint8)
    sfx_lut[sfx_ids] = 255
    sfx_mask = sfx_lut[labels]

    sfx_boxes = []
    if sfx_verified:
        sfx_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (35, 20))
        sfx_grouped = cv2.dilate(sfx_mask, sfx_kernel, iterations=1)
        sfx_cnts, _ = cv2.findContours(sfx_grouped, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in sfx_cnts:
            sx, sy, sw, sh = cv2.boundingRect(cnt)
            in_sfx = [b for b in sfx_verified if sx <= b[1] and (b[1] + b[3]) <= (sx + sw) and sy <= b[2] and (b[2] + b[4]) <= (sy + sh)]
            if len(in_sfx) >= 4 and sw > 90:
                # Считываем изгиб (дугу) текста по центрам букв внутри SFX-блока
                arch_val = 0
                try:
                    pts_x = np.array([b[1] + b[3] / 2.0 for b in in_sfx], dtype=np.float64)
                    pts_y = np.array([b[2] + b[4] / 2.0 for b in in_sfx], dtype=np.float64)
                    if len(pts_x) >= 3 and (pts_x.max() - pts_x.min()) > 30:
                        mid_x = (pts_x.max() + pts_x.min()) / 2.0
                        half_w = (pts_x.max() - pts_x.min()) / 2.0
                        nx = (pts_x - mid_x) / half_w  # [-1, 1]
                        coeffs = np.polyfit(nx, pts_y, 2)
                        # coeffs[0] > 0: края ниже середины
                        if abs(coeffs[0]) >= 5.0:
                            arch_val = int(max(-120, min(120, round(coeffs[0]))))
                except Exception:
                    arch_val = 0
                sfx_boxes.append((max(0, sx - 6), max(0, sy - 6), min(W - sx, sw + 16), min(H - sy, sh + 14), arch_val))

    erase_ids = []

    for (bx, by, bw, bh) in valid_bubbles:
        for i in range(1, num_labels):
            if barrier_lut[i]:
                continue
            cx, cy, cw, ch, carea = stats[i]
            if (cx >= bx - 4 and (cx + cw) <= (bx + bw + 6) and
                cy >= by - 4 and (cy + ch) <= (by + bh + 4)):
                center_x = bx + bw // 2
                center_y = by + bh // 2
                line_check = np.zeros_like(barrier_mask)
                cv2.line(line_check, (center_x, center_y), (cx + cw // 2, cy + ch // 2), 255, 1)
                if np.any((line_check > 0) & (barrier_mask > 0)):
                    continue
                if ch < 5:
                    p = 4
                    y1, y2 = max(0, cy - p), min(H, cy + ch + p)
                    x1, x2 = max(0, cx - p), min(W, cx + cw + p)
                    if np.mean(white_mask[y1:y2, x1:x2]) < 185:
                        continue
                erase_ids.append(i)

    for sfx_b in sfx_boxes:
        sx, sy, sw, sh = sfx_b[0], sfx_b[1], sfx_b[2], sfx_b[3]
        for i in range(1, num_labels):
            cx, cy, cw, ch, carea = stats[i]
            if cx >= sx and (cx + cw) <= (sx + sw) and cy >= sy and (cy + ch) <= (sy + sh):
                if ch <= sh * 0.98 and cw <= sw * 0.45:
                    erase_ids.append(i)

    erase_lut = np.zeros(num_labels, dtype=np.uint8)
    erase_lut[erase_ids] = 255
    erase_mask = erase_lut[labels]

    def sort_reading_order(box_list):
        box_list.sort(key=lambda b: b[1])
        rows = []
        row_thresh = max(70, min(150, int(H * 0.18)))
        for b in box_list:
            placed = False
            for r in rows:
                avg_y = np.mean([item[1] for item in r])
                if abs(b[1] - avg_y) < row_thresh:
                    r.append(b)
                    placed = True
                    break
            if not placed:
                rows.append([b])
        res = []
        for r in rows:
            r.sort(key=lambda b: b[0])
            res.extend(r)
        return res

    sorted_bubbles = sort_reading_order(valid_bubbles)
    sorted_sfx = sort_reading_order(sfx_boxes)

    return img, erase_mask, sorted_bubbles, sorted_sfx


def clean_selected_bubbles(orig_img, erase_mask, boxes_to_clean):
    cleaned = orig_img.copy()
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    for b in boxes_to_clean:
        x, y, w, h = b[0], b[1], b[2], b[3]
        roi = erase_mask[y:y+h, x:x+w]
        dilated = cv2.dilate(roi, kernel, iterations=1)
        cleaned[y:y+h, x:x+w][dilated > 0] = [255, 255, 255]

    return cleaned


class ComicText(QGraphicsTextItem):
    HANDLE_SIZE = 10

    def __init__(self, text, is_bubble=True, box=None, main_win=None, is_outlined=None, arch_amount=0):
        super().__init__()
        self.main_win = main_win
        self.is_bubble = is_bubble
        # По умолчанию для звуков/эмоций (ХАХАХА!) используется шрифт Mp Manga Bold Shadow
        self.is_outlined = (not is_bubble) if is_outlined is None else is_outlined

        self.current_stretch = 100
        self.current_italic = False
        self.bold_level = 0  # Уровень жирности: 0 = обычный, 1..10 = плавное утолщение на каждый клик
        self.arch_amount = arch_amount

        formatted = hyphenate_text(text.upper()) if is_bubble else text.upper()
        self.setPlainText(formatted)

        self.box_width = box[2] if box else 150
        self.current_size = 11.0 if is_bubble else 28.0

        self.drag_mode = None
        self.start_mouse_pos = QPointF()
        self.start_item_pos = QPointF()
        self.start_width = self.box_width
        self.start_size = self.current_size
        self.text_before_edit = ""

        self.setFlags(
            QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsTextItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setAcceptHoverEvents(True)

        if box and is_bubble:
            bx, by, bw, bh = box
            safe_w = max(70, bw * 0.94)
            safe_h = max(32, bh * 0.96)
            self.auto_fit_font(safe_w, safe_h)

            rect = super().boundingRect()
            pos_x = bx + (bw - rect.width()) / 2
            pos_y = by + (bh - rect.height()) / 2 - 2
            self.setPos(pos_x, pos_y)
        elif box and not is_bubble:
            bx, by, bw, bh = box[0], box[1], box[2], box[3]
            if len(box) >= 5 and self.arch_amount == 0:
                self.arch_amount = box[4]
            self.auto_fit_sfx(bw, bh)
            rect = super().boundingRect()
            pos_x = bx + (bw - rect.width()) / 2
            pos_y = by + (bh - rect.height()) / 2
            self.setPos(pos_x, pos_y)
        else:
            bx, by = (box[0], box[1]) if box else (60, 60)
            self.setPos(bx, by)
            self.update_style()

    def boundingRect(self):
        r = super().boundingRect()
        pad_y = abs(self.arch_amount) + 18 if self.arch_amount != 0 else 8
        pad_x = 18 if self.arch_amount != 0 else 8
        return r.adjusted(-pad_x, -pad_y, pad_x, pad_y)

    def auto_fit_font(self, target_w, target_h):
        self.box_width = target_w
        best_size = 6.5

        for size_x2 in range(44, 12, -1):
            size = size_x2 / 2.0
            self.current_size = size
            self.update_style()

            rect = super().boundingRect()
            if rect.height() <= target_h * 1.06 and rect.width() <= target_w * 1.05:
                best_size = size
                break

        self.current_size = best_size
        self.update_style()

    def auto_fit_sfx(self, target_w, target_h):
        best_size = 20.0
        for size in range(58, 14, -1):
            self.current_size = float(size)
            self.update_style()
            rect = super().boundingRect()
            if rect.width() <= target_w * 1.08 and rect.height() <= target_h * 1.15:
                best_size = float(size)
                break
        self.current_size = best_size
        self.update_style()

    def get_bold_pen_width(self):
        if self.bold_level <= 0:
            return 0.0
        return self.bold_level * max(0.32, self.current_size * 0.032)

    def apply_outline_format(self):
        """Синхронизирует шрифт документа (без залипания старого стиля) и применяет плавную жирность"""
        doc = self.document()
        cursor = QTextCursor(doc)
        cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextCharFormat()
        fmt.setFont(self.font())
        fmt.setForeground(QBrush(QColor("black")))
        if self.bold_level > 0:
            pen_w = self.get_bold_pen_width()
            pen = QPen(
                QColor("black"), pen_w,
                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin
            )
            fmt.setTextOutline(pen)
        else:
            fmt.setTextOutline(QPen(Qt.PenStyle.NoPen))
        # setCharFormat полностью заменяет старый стиль
        cursor.setCharFormat(fmt)

    def toggle_outline(self):
        if self.is_bubble:
            # Для обычных реплик (Peanuts by me) кнопка переключает жирность (0 <-> 2)
            self.bold_level = 2 if self.bold_level == 0 else 0
            self.is_outlined = False
        else:
            # для эмоций/SFX переключаю между Mp Manga Bold Shadow и обычным MPMangaFont-Bold
            self.is_outlined = not self.is_outlined
        self.update_style()

    def update_style(self):
        self.prepareGeometryChange()
        if self.is_bubble:
            font_key = "peanuts"
        else:
            font_key = "manga_shadow" if self.is_outlined else "manga"

        font_name = FONTS[font_key]
        style_name = FONT_STYLES.get(font_key, "")

        if style_name:
            f = QFontDatabase.font(font_name, style_name, max(6, int(round(self.current_size))))
        else:
            f = QFont(font_name)
        f.setPointSizeF(max(5.0, self.current_size))
        f.setStretch(self.current_stretch)
        f.setItalic(self.current_italic)

        self.setFont(f)
        self.document().setDefaultFont(f)
        self.setDefaultTextColor(QColor("black"))

        if self.is_bubble:
            self.setTextWidth(max(45, self.box_width))
            doc = self.document()
            opt = doc.defaultTextOption()
            opt.setAlignment(Qt.AlignmentFlag.AlignCenter)
            opt.setWrapMode(opt.WrapMode.WordWrap)
            doc.setDefaultTextOption(opt)
        else:
            self.setTextWidth(-1)

        self.apply_outline_format()

        if self.scene():
            self.scene().update()
        else:
            self.update()

    def width_handle_rect(self):
        r = super().boundingRect()
        s = self.HANDLE_SIZE
        return QRectF(r.right() - s, r.center().y() - s / 2, s, s)

    def scale_handle_rect(self):
        r = super().boundingRect()
        s = self.HANDLE_SIZE
        return QRectF(r.right() - s, r.bottom() - s, s, s)

    def hoverMoveEvent(self, event):
        if self.isSelected():
            pos = event.pos()
            if self.scale_handle_rect().contains(pos):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                return
            elif self.width_handle_rect().contains(pos):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                return
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().hoverMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.main_win:
            self.main_win.push_undo_state()
        self.text_before_edit = self.toPlainText()
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event):
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        if self.is_bubble:
            self.setPlainText(hyphenate_text(self.toPlainText()))
        self.apply_outline_format()
        super().focusOutEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.main_win:
                self.main_win.push_undo_state()
            self.start_item_pos = self.pos()
            if self.isSelected():
                pos = event.pos()
                if self.scale_handle_rect().contains(pos):
                    self.drag_mode = "scale"
                    self.start_mouse_pos = event.scenePos()
                    self.start_size = self.current_size
                    self.start_width = self.box_width
                    event.accept()
                    return
                elif self.width_handle_rect().contains(pos):
                    self.drag_mode = "width"
                    self.start_mouse_pos = event.scenePos()
                    self.start_width = self.box_width
                    event.accept()
                    return
        self.drag_mode = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_mode == "width":
            dx = event.scenePos().x() - self.start_mouse_pos.x()
            self.box_width = max(45, self.start_width + dx)
            self.update_style()
            event.accept()
            return
        elif self.drag_mode == "scale":
            dy = event.scenePos().y() - self.start_mouse_pos.y()
            dx = event.scenePos().x() - self.start_mouse_pos.x()
            delta = (dx + dy) * 0.08
            new_size = max(5.0, min(72.0, self.start_size + delta))
            self.current_size = new_size
            self.update_style()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drag_mode:
            self.drag_mode = None
            if self.scene():
                self.scene().update()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self.pos() == self.start_item_pos:
            if self.main_win and self.main_win.undo_stack:
                self.main_win.undo_stack.pop()
                self.main_win.update_undo_button()
        super().mouseReleaseEvent(event)

    def change_size(self, delta):
        self.current_size = max(5.0, self.current_size + delta)
        self.update_style()

    def change_width(self, delta):
        if self.is_bubble:
            self.box_width = max(45, self.box_width + delta)
            self.update_style()

    def toggle_italic(self):
        self.current_italic = not self.current_italic
        self.update_style()
        
    def change_stretch(self, delta):
        self.current_stretch = max(50, min(400, self.current_stretch + delta))
        self.update_style()
        
    def change_weight(self, delta):
        step = 1 if delta > 0 else -1
        self.bold_level = max(0, min(10, self.bold_level + step))
        self.update_style()

    def set_arch(self, arch_val):
        self.prepareGeometryChange()
        self.arch_amount = max(-150, min(150, int(arch_val)))
        if self.scene():
            self.scene().update()
        else:
            self.update()

    def paint(self, painter, option, widget=None):
        opt = QStyleOptionGraphicsItem(option)
        opt.state &= ~QStyle.StateFlag.State_Selected
        opt.state &= ~QStyle.StateFlag.State_HasFocus
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        is_editing = (self.textInteractionFlags() == Qt.TextInteractionFlag.TextEditorInteraction)
        if self.arch_amount != 0 and not is_editing:
            r = super().boundingRect()
            lines = self.toPlainText().splitlines()
            if not lines:
                lines = [""]
            fm = QFontMetrics(self.font())
            line_h = fm.lineSpacing()
            total_h = line_h * len(lines)
            start_y = r.center().y() - total_h / 2.0 + fm.ascent()

            painter.save()
            painter.setFont(self.font())
            painter.setPen(QColor("black"))

            for li, line in enumerate(lines):
                if not line:
                    continue
                char_widths = [fm.horizontalAdvance(ch) for ch in line]
                total_w = sum(char_widths)
                if total_w <= 0:
                    continue
                half_w = max(1.0, total_w / 2.0)
                cur_x = -half_w
                base_y = start_y + li * line_h
                cx_center = r.center().x()

                for ch, cw in zip(line, char_widths):
                    char_mid_x = cur_x + cw / 2.0
                    t = char_mid_x / half_w  # [-1, 1]
                    # Парабола: при arch_amount > 0 середина выше краев (арка вверх) ебаная математика
                    dy = self.arch_amount * (t * t - 0.5)
                    # Производная dy/dx для угла наклона каждой буквы
                    slope = (2.0 * self.arch_amount * t) / half_w
                    angle_deg = math.degrees(math.atan(slope))

                    painter.save()
                    painter.translate(cx_center + char_mid_x, base_y + dy)
                    painter.rotate(angle_deg)
                    if self.bold_level > 0:
                        path = QPainterPath()
                        path.addText(QPointF(-cw / 2.0, 0), self.font(), ch)
                        pen_w = self.get_bold_pen_width()
                        painter.setPen(QPen(
                            QColor("black"), pen_w,
                            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin
                        ))
                        painter.setBrush(QBrush(QColor("black")))
                        painter.drawPath(path)
                    else:
                        painter.drawText(QPointF(-cw / 2.0, 0), ch)
                    painter.restore()

                    cur_x += cw

            painter.restore()
        else:
            super().paint(painter, opt, widget)

        if self.isSelected():
            r = super().boundingRect()
            painter.save()
            pen = QPen(QColor("#00a8ff"), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r)

            painter.setPen(QPen(QColor("white"), 1))
            painter.setBrush(QBrush(QColor("#00a8ff")))
            painter.drawRect(self.width_handle_rect())

            painter.setBrush(QBrush(QColor("#00e676")))
            painter.drawRect(self.scale_handle_rect())
            painter.restore()


class StripCanvasView(QGraphicsView):
    def __init__(self, scene, main_win):
        super().__init__(scene)
        self.main_win = main_win
        self.erasing = False
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton and self.main_win.cleaned_pixmap:
            self.main_win.push_undo_state()
            self.erasing = True
            self.erase_at(event.pos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.erasing and self.main_win.cleaned_pixmap:
            self.erase_at(event.pos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton and self.erasing:
            self.erasing = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def erase_at(self, view_pos):
        scene_pt = self.mapToScene(view_pos)
        self.main_win.paint_white_spot(int(scene_pt.x()), int(scene_pt.y()), radius=12)



# ОРИГИНАЛЬНЫЙ КОД ВТОРОЙ ПРОГРАММЫ: Multi tool for Pinats by Alimtair (Wand / ImageMagick + Tkinter)

import datetime
try:
    from wand.image import Image as WandImage
except ImportError:
    WandImage = None
from PIL import Image as pil


class constants:
    MIN_SQ_W = 500
    RES = 'result/'
    ACOM_X = 1024
    ACOM_Y = 223
    ACOM_W_Y = 705
    GO_X = 400
    GO_Y = 250
    W_GO_X = 400
    W_GO_Y = 250
    WHITE_PIXEL = 'srgb(250,250,250)'


class Level:
    def __init__(self, img):
        self.img = img
        self.clone = self.img.clone()

    def invert(self):
        img_inverted = self.clone
        img_inverted.level(0.6, 0.5, gamma=1)
        return img_inverted

    def contrast(self):
        img_contrast = self.img
        img_contrast.level(0.23529411764705882, 0.9098039215686274)
        return img_contrast


class Start:
    def __init__(self, path, folder, contrast, operation, date, logger):
        self.path = path
        self.folder = folder
        self.contrast = contrast
        self.operation = operation
        self.date = date
        self.log = logger

    def pret_start(self):
        global WandImage
        if WandImage is None:
            if ensure_imagemagick_engine():
                from wand.image import Image as WandImage
            else:
                raise RuntimeError("Движок ImageMagick не установлен! Установи ImageMagick для работы этой функции.")
        self.original = WandImage(filename=self.file)
        self.edit_img = self.original.clone()
        self.edit_img.format = 'png'
        if self.contrast:
            self.level = Level(self.edit_img)
            self.edit_img = self.level.contrast()

    def start_multi(self):
        os.makedirs(constants.RES, exist_ok=True)
        initial_date = Operation()
        initial_date.give_date(date=self.date)
        try:
            if self.path[0].isdigit():
                operation = Operation(
                    command=self.operation,
                    file_name=self.path,
                    logger=self.log
                )
                operation.operr()
            elif self.folder:
                file_list = os.listdir(self.path)
                file_list.sort()
                for self.file_name in file_list:
                    if self.file_name.endswith('jpg') or self.file_name.endswith('png') or self.file_name.endswith('gif'):
                        self.file = self.path + '/' + self.file_name
                        self.pret_start()
                        operation = Operation(
                            img=self.edit_img,
                            command=self.operation,
                            file_name=self.file_name,
                            logger=self.log
                        )
                        operation.operr()
            else:
                self.file = self.path
                self.pret_start()
                lst = self.file.split(sep='/')
                self.file_name = lst[-1]
                operation = Operation(
                    img=self.edit_img,
                    command=self.operation,
                    file_name=self.file_name,
                    logger=self.log
                )
                operation.operr()
        except Exception as e:
            self.log(str(e))


class Operation:
    cur_date = 'nothing'

    def __init__(self, logger='none', img='none', command='none', file_name='none'):
        self.edit_img = img
        self.command = command
        self.file_name = file_name
        self.log = logger
        if img != 'none':
            self.level = Level(self.edit_img)
            self.inverted = self.level.invert()

    @classmethod
    def give_date(cls, date):
        Operation.cur_date = date

    def operr(self):
        command = self.command
        if command == 'slice':
            if self.file_name[0] == 'w':
                self.clone_1 = self.edit_img.clone()
                self.w_slice()
            else:
                self.clone_1 = self.edit_img.clone()
                self.clone_2 = self.edit_img.clone()
                self.clone_3 = self.edit_img.clone()
                self.slice()
        elif command == 'date':
            self.date()
        elif command == 'square':
            self.clone_1 = self.edit_img.clone()
            self.clone_2 = self.edit_img.clone()
            self.square()
        elif command == 'acomics':
            self.clone_1 = self.edit_img.clone()
            self.acomics()
        elif command == 'add_to_validation_list':
            self.add_to_validation_list()
        elif command == 'validate':
            self.validate()
        else:
            self.img_save(to_save=self.edit_img)

    @staticmethod
    def w_and_h(inverte, x, y, weekend=False):
        marker = 0
        marker = inverte.width - 2
        while inverte[marker, y + 10].string < constants.WHITE_PIXEL:
            marker -= 2
        w = marker - x
        if not weekend:
            h = int((inverte.height - 3 * y) / 3)
            marker = h + y + 10
            while inverte[x + 15, marker].string < constants.WHITE_PIXEL:
                marker -= 2
            h = marker - y
        else:
            marker = inverte.height
            while inverte[x + 20, marker - 1].string <= constants.WHITE_PIXEL and marker > 0:
                marker -= 3
            h = marker - y
        w += 30
        h += 40
        return (w, h)

    @staticmethod
    def upper_left(inverte, mark_x, mark_y, x=0, y=0):
        while inverte[x, mark_y].string < constants.WHITE_PIXEL:
            x += 2
        while inverte[mark_x, y].string < constants.WHITE_PIXEL:
            y += 2
        return (x, y)

    def slice(self):
        strips = [self.clone_1, self.clone_2, self.clone_3]
        mark_x = constants.GO_X
        mark_y = constants.GO_Y
        x, y = self.upper_left(inverte=self.inverted, mark_x=mark_x, mark_y=mark_y)
        space = y
        w, h = self.w_and_h(inverte=self.inverted, x=x, y=y)
        for i in range(3):
            if i != 0:
                x, y = self.upper_left(inverte=self.inverted, mark_x=mark_x, mark_y=mark_y, y=y)
            x -= 15
            y -= 20
            strips[i].crop(x, y, width=w, height=h)
            if i == 0:
                mark_y = 2 * space + h
                y = space + h
            elif i == 1:
                mark_y = int(strips[i + 1].height - space - 0.7 * h)
                y = strips[i + 1].height - space - h
            self.img_save(to_save=strips[i], special_arg=True, i=i)

    def w_slice(self):
        mark_x = constants.W_GO_X
        mark_y = constants.W_GO_Y
        x, y = self.upper_left(inverte=self.inverted, mark_x=mark_x, mark_y=mark_y)
        w, h = self.w_and_h(inverte=self.inverted, x=x, y=y, weekend=True)
        x -= 15
        y -= 20
        self.edit_img.crop(x, y, width=w, height=h)
        self.img_save(to_save=self.edit_img)

    def square(self):
        w = int(self.clone_1.width / 2)
        h = self.clone_1.height
        mark_x = constants.GO_X
        mark_y = constants.GO_Y
        x, y = self.upper_left(inverte=self.inverted, mark_x=mark_x, mark_y=mark_y)
        self.clone_1.crop(x, 0, width=w, height=h)
        self.clone_2.crop(w, 0, width=w, height=h)
        self.level = Level(self.clone_2)
        inverted_clone_2 = self.level.invert()
        x, y = self.upper_left(inverte=inverted_clone_2, mark_x=mark_x, mark_y=mark_y)
        self.clone_2.crop(x, y, width=w, height=h)
        w1 = self.clone_1.width
        w2 = self.clone_2.width
        w_res = min(w1, w2)
        h_res = self.clone_1.height + self.clone_2.height
        cntrl_point = h
        res = WandImage(width=w_res + 5, height=h_res, background='white')
        res.composite(image=self.clone_2, left=5, top=cntrl_point)
        res.composite(image=self.clone_1, left=5, top=0)
        self.img_save(to_save=res)

    def acomics(self):
        h = self.clone_1.height
        if h < 1000:
            self.clone_1.resize(constants.ACOM_X, constants.ACOM_Y)
        else:
            self.clone_1.resize(constants.ACOM_X, constants.ACOM_W_Y)
        self.img_save(to_save=self.clone_1)

    def img_save(self, to_save, special_arg=False, i=False):
        os.makedirs(constants.RES, exist_ok=True)
        if special_arg:
            self.save = self.file_name[:-4] + ' ' + str(i) + '.png'
        else:
            self.save = self.file_name[:-4] + '.png'
        self.save = constants.RES + self.save
        to_save.save(filename=self.save)

    def date(self):
        self.file_name = 'pe' + Operation.cur_date + '.png'
        self.img_save(to_save=self.edit_img)
        lst = Operation.cur_date.split(sep='-')
        year = int(lst[0])
        month = int(lst[1])
        day = int(lst[2])
        D = datetime.date(year, month, day)
        delta = datetime.timedelta(days=1)
        D = D + delta
        year = str(D.year)
        month = self.add_zero(date=D.month)
        day = self.add_zero(date=D.day)
        Operation.cur_date = year + '-' + month + '-' + day

    def add_to_validation_list(self):
        file_name = self.file_name[:-4]
        if file_name[0].isdigit() and len(file_name) == 10:
            date = file_name
        elif len(file_name) == 12:
            date = file_name[2:]
        else:
            self.log(
                f'Стрип не правльно назван или \nне правильного формата, его название\n'
                f'{file_name}.\nСтрип должен быть peYYYY-MM-DD.png или\nYYYY-MM-DD.png. Обязательно пнг'
            )
            return 0
        if not os.path.exists('validation list.txt'):
            with open('validation list.txt', 'w', encoding='utf-8') as f:
                f.write('')
        with open('validation list.txt', 'r+', encoding='utf-8') as file:
            existing_data = file.read().strip()
            validation_set = set(x.strip() for x in existing_data.split(',') if x.strip())
            validation_set.add(date)
            file.seek(0)
            file.truncate()
            file_text = ', '.join(list(validation_set))
            file.write(file_text)
        self.log(f'Стрип по дате: {date} добавлен в лист')

    def validate(self):
        file_name = self.file_name
        if file_name[0].isdigit():
            date = file_name[0:10]
        else:
            date = file_name[2:12]
        with open('validation list.txt', 'r', encoding='utf-8') as file:
            existing_data = file.read().strip()
            validation_set = set(x.strip() for x in existing_data.split(',') if x.strip())
            if date in validation_set:
                self.log(f'Стрип по дате: {date} уже переведен')
            else:
                self.log(f'Стрип по дате: {date} не переведен')

    @staticmethod
    def add_zero(date):
        if date < 10:
            date = '0' + str(date)
        return str(date)


from PyQt6.QtWidgets import (
    QTabWidget, QLineEdit, QCheckBox, QRadioButton,
    QButtonGroup, QGroupBox, QTextEdit, QGridLayout
)


class MultiToolQtTab(QWidget):
    """Вкладка Multi tool for Pinats by Alimtair внутри общего окна (вызывает оригинальный Start / Operation на Wand + ImageMagick)"""
    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        top_grid = QHBoxLayout()
        left_col = QVBoxLayout()

        # 1. Folder / File + Browse
        path_box = QGroupBox("Folder / File")
        path_v = QVBoxLayout(path_box)

        mode_row = QHBoxLayout()
        self.rb_folder = QRadioButton("Folder")
        self.rb_file = QRadioButton("File")
        self.rb_folder.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.rb_folder, 1)
        self.mode_group.addButton(self.rb_file, 0)
        mode_row.addWidget(self.rb_folder)
        mode_row.addWidget(self.rb_file)
        mode_row.addStretch()
        path_v.addLayout(mode_row)

        browse_row = QHBoxLayout()
        self.edit_path = QLineEdit()
        self.btn_browse = QPushButton("Browse")
        self.btn_browse.clicked.connect(self.browse)
        browse_row.addWidget(self.edit_path, stretch=1)
        browse_row.addWidget(self.btn_browse)
        path_v.addLayout(browse_row)
        left_col.addWidget(path_box)

        # 2. Decoration + Date
        opts_row = QHBoxLayout()

        dec_box = QGroupBox("Decoration")
        dec_v = QVBoxLayout(dec_box)
        self.chk_contrast = QCheckBox("contrast")
        dec_v.addWidget(self.chk_contrast)
        opts_row.addWidget(dec_box)

        date_box = QGroupBox("Date")
        date_v = QVBoxLayout(date_box)
        self.edit_date = QLineEdit("YYYY-MM-DD")
        date_v.addWidget(self.edit_date)
        opts_row.addWidget(date_box)

        left_col.addLayout(opts_row)

        # 3. Operation
        op_box = QGroupBox("Operation")
        op_v = QVBoxLayout(op_box)
        self.op_group = QButtonGroup(self)
        ops = [
            ("Slice", "slice"),
            ("Date", "date"),
            ("Square", "square"),
            ("acomics", "acomics"),
            ("add to validation list", "add_to_validation_list"),
            ("validate", "validate"),
            ("Nothing", "nothing"),
        ]
        self.op_radios = {}
        for title, val in ops:
            rb = QRadioButton(title)
            if val == "slice":
                rb.setChecked(True)
            self.op_group.addButton(rb)
            self.op_radios[rb] = val
            op_v.addWidget(rb)
        left_col.addWidget(op_box)

        # 4. Go button
        btn_row = QHBoxLayout()
        self.btn_go = QPushButton("Go")
        self.btn_go.setStyleSheet("font-weight: bold; padding: 8px 24px;")
        self.btn_go.clicked.connect(self.go_Multi)
        btn_row.addWidget(self.btn_go)
        btn_row.addStretch()

        left_col.addLayout(btn_row)
        left_col.addStretch()
        top_grid.addLayout(left_col, stretch=3)

        # Output zone
        right_col = QVBoxLayout()
        right_col.addWidget(QLabel("Output zone"))
        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        right_col.addWidget(self.output_box)
        top_grid.addLayout(right_col, stretch=2)

        layout.addLayout(top_grid)

    def browse(self):
        if self.rb_folder.isChecked():
            cur_direktory = QFileDialog.getExistingDirectory(self, "Select Folder")
            if cur_direktory:
                self.edit_path.setText(cur_direktory)
        else:
            cur_file, _ = QFileDialog.getOpenFileName(self, "Select File")
            if cur_file:
                self.edit_path.setText(cur_file)

    def get_operation_value(self):
        for rb, val in self.op_radios.items():
            if rb.isChecked():
                return val
        return "slice"

    def log(self, message: str):
        self.output_box.append(str(message))

    def go_Multi(self):
        go = Start(
            path=self.edit_path.text(),
            folder=bool(self.rb_folder.isChecked()),
            contrast=1 if self.chk_contrast.isChecked() else 0,
            operation=self.get_operation_value(),
            date=self.edit_date.text(),
            logger=self.log
        )
        go.start_multi()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RUS PEANUTS — Auto-Typesetter")
        self.resize(1320, 860)
        self.setAcceptDrops(True)

        self.orig_cv_img = None
        self.current_cv_img = None
        self.erase_mask = None
        self.detected_boxes = []
        self.detected_sfx = []
        self.current_txt_path = None
        self.cleaned_pixmap = None
        self.pixmap_item = None
        self.text_blocks = []
        self.undo_stack = []

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 6, 10, 10)

        #Фиксированный логотип по центру сверху
        header_layout = QHBoxLayout()
        header_layout.addStretch()
        self.lbl_logo = QLabel()
        self.lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.lbl_logo)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        self.init_fixed_logo()

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.tab_typesetter = QWidget()
        ts_layout = QVBoxLayout(self.tab_typesetter)
        ts_layout.setContentsMargins(0, 4, 0, 0)

        #Панель управления
        bar = QHBoxLayout()

        self.btn_img = QPushButton("1. Загрузить Стрип")
        self.btn_img.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_img.clicked.connect(self.open_image_dialog)
        bar.addWidget(self.btn_img)

        self.btn_txt = QPushButton("2. Загрузить Перевод (.txt)")
        self.btn_txt.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_txt.clicked.connect(self.open_txt_dialog)
        bar.addWidget(self.btn_txt)

        bar.addSpacing(8)

        self.btn_undo = QPushButton("↩ Отменить (Ctrl+Z)")
        self.btn_undo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(self.undo_action)
        bar.addWidget(self.btn_undo)

        bar.addSpacing(8)

        self.btn_plus = QPushButton("+ Текст")
        self.btn_plus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_plus.clicked.connect(lambda: self.adjust_font(0.5))
        bar.addWidget(self.btn_plus)

        self.btn_minus = QPushButton("− Текст")
        self.btn_minus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_minus.clicked.connect(lambda: self.adjust_font(-0.5))
        bar.addWidget(self.btn_minus)

        self.btn_wider = QPushButton("↔ Шире")
        self.btn_wider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_wider.clicked.connect(lambda: self.adjust_width(10))
        bar.addWidget(self.btn_wider)

        self.btn_narrow = QPushButton(">< Уже")
        self.btn_narrow.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_narrow.clicked.connect(lambda: self.adjust_width(-10))
        bar.addWidget(self.btn_narrow)

        bar.addSpacing(8)

        self.btn_italic = QPushButton("I Курсив")
        self.btn_italic.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_italic.clicked.connect(self.toggle_italic)
        bar.addWidget(self.btn_italic)

        self.btn_str_plus = QPushButton("+ Растяг")
        self.btn_str_plus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_str_plus.clicked.connect(lambda: self.adjust_stretch(10))
        bar.addWidget(self.btn_str_plus)

        self.btn_str_minus = QPushButton("- Растяг")
        self.btn_str_minus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_str_minus.clicked.connect(lambda: self.adjust_stretch(-10))
        bar.addWidget(self.btn_str_minus)

        self.btn_wt_plus = QPushButton("+ Жирность")
        self.btn_wt_plus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_wt_plus.clicked.connect(lambda: self.adjust_weight(1))
        bar.addWidget(self.btn_wt_plus)

        self.btn_wt_minus = QPushButton("- Жирность")
        self.btn_wt_minus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_wt_minus.clicked.connect(lambda: self.adjust_weight(-1))
        bar.addWidget(self.btn_wt_minus)

        self.btn_outline = QPushButton("Shadow / Обычный")
        self.btn_outline.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_outline.setToolTip("Для эмоций: переключить Shadow / MPMangaFont-Bold. Для реплик: сделать текст жирнее")
        self.btn_outline.clicked.connect(self.toggle_selected_outline)
        bar.addWidget(self.btn_outline)

        self.btn_arch = QPushButton("Изгиб текста")
        self.btn_arch.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_arch.setToolTip("Изогнуть выделенный текст дугой вверх или вниз")
        self.btn_arch.clicked.connect(self.open_arch_dialog)
        bar.addWidget(self.btn_arch)

        bar.addSpacing(8)

        self.btn_save = QPushButton("Сохранить (PNG)")
        self.btn_save.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_save.clicked.connect(self.save_result)
        bar.addWidget(self.btn_save)

        bar.addSpacing(12)

        self.btn_orig = QPushButton("Показать оригинал")
        self.btn_orig.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_orig.setCheckable(True)
        self.btn_orig.clicked.connect(self.toggle_original)
        bar.addWidget(self.btn_orig)
        
        self.btn_guide = QPushButton("Руководство")
        self.btn_guide.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_guide.clicked.connect(self.show_guide)
        bar.addWidget(self.btn_guide)

        self.btn_about = QPushButton("О нас")
        self.btn_about.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_about.clicked.connect(self.show_about)
        bar.addWidget(self.btn_about)

        ts_layout.addLayout(bar)

        self.lbl_status = QLabel(
            "Добро Пожаловать!"
        )
        self.lbl_status.setStyleSheet("color: #333; font-weight: bold; font-size: 12px;")
        ts_layout.addWidget(self.lbl_status)

        self.scene = QGraphicsScene(self)
        self.view = StripCanvasView(self.scene, self)
        ts_layout.addWidget(self.view)

        self.tab_multitool = MultiToolQtTab(self)
        self.tabs.addTab(self.tab_typesetter, "1. RUS PEANUTS — Auto-Typesetter")
        self.tabs.addTab(self.tab_multitool, "2. Multi tool for Pinats by Alimtair (ImageMagick)")

        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self.undo_action)

    def init_fixed_logo(self):
        pix_logo = load_b64_pixmap(EMBEDDED_LOGO_B64)
        if not pix_logo.isNull():
            self.lbl_logo.setPixmap(pix_logo)
        pix_icon = load_b64_pixmap(EMBEDDED_APP_ICON_B64)
        if not pix_icon.isNull():
            self.setWindowIcon(QIcon(pix_icon))

    #Система отмены действий
    def push_undo_state(self):
        if self.current_cv_img is None:
            return
        blocks_snapshot = []
        for b in self.text_blocks:
            if b.scene() == self.scene:
                blocks_snapshot.append({
                    "text": b.toPlainText(),
                    "is_bubble": b.is_bubble,
                    "is_outlined": b.is_outlined,
                    "pos_x": b.pos().x(),
                    "pos_y": b.pos().y(),
                    "box_width": b.box_width,
                    "current_size": b.current_size,
                    "current_stretch": getattr(b, "current_stretch", 100),
                    "bold_level": getattr(b, "bold_level", 0),
                    "current_italic": getattr(b, "current_italic", False),
                    "arch_amount": getattr(b, "arch_amount", 0),
                    "selected": b.isSelected()
                })
        state = {
            "cv_img": self.current_cv_img.copy(),
            "blocks": blocks_snapshot
        }
        self.undo_stack.append(state)
        if len(self.undo_stack) > 40:
            self.undo_stack.pop(0)
        self.update_undo_button()

    def update_undo_button(self):
        self.btn_undo.setEnabled(len(self.undo_stack) > 0)

    def toggle_original(self, checked):
        if self.orig_cv_img is None or not self.cleaned_pixmap:
            self.btn_orig.setChecked(False)
            return

        if checked:
            if not hasattr(self, 'orig_qpixmap'):
                self.orig_qpixmap = self.cv2_to_qpixmap(self.orig_cv_img)
            self.pixmap_item.setPixmap(self.orig_qpixmap)
            for b in self.text_blocks:
                b.setVisible(False)
            self.btn_orig.setText("Вернуть результат")
        else:
            self.pixmap_item.setPixmap(self.cleaned_pixmap)
            for b in self.text_blocks:
                b.setVisible(True)
            self.btn_orig.setText("Показать оригинал")

    def undo_action(self):
        if not self.undo_stack:
            return
        state = self.undo_stack.pop()
        self.update_undo_button()

        self.current_cv_img = state["cv_img"].copy()
        self.cleaned_pixmap = self.cv2_to_qpixmap(self.current_cv_img)

        self.scene.clear()
        self.text_blocks.clear()
        self.pixmap_item = self.scene.addPixmap(self.cleaned_pixmap)
        self.scene.setSceneRect(QRectF(self.cleaned_pixmap.rect()))

        for b_data in state["blocks"]:
            block = ComicText(
                text=b_data["text"],
                is_bubble=b_data["is_bubble"],
                box=None,
                main_win=self,
                is_outlined=b_data["is_outlined"]
            )
            block.box_width = b_data["box_width"]
            block.current_size = b_data["current_size"]
            block.current_stretch = b_data.get("current_stretch", 100)
            block.bold_level = b_data.get("bold_level", 0)
            block.current_italic = b_data.get("current_italic", False)
            block.arch_amount = b_data.get("arch_amount", 0)
            block.setPlainText(b_data["text"])
            block.update_style()
            block.setPos(b_data["pos_x"], b_data["pos_y"])
            block.setSelected(b_data["selected"])
            self.scene.addItem(block)
            self.text_blocks.append(block)

        self.lbl_status.setText("Действие отменено!")

    #Окна "Руководство" (картинка слева) и "О нас" (картинка справа)
    def show_guide(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Как тут всё работает")
        dlg.setMinimumWidth(680)
        dlg.setStyleSheet("QDialog { background-color: white; } QLabel { color: #111; font-size: 13px; }")

        main_v = QVBoxLayout(dlg)
        content_h = QHBoxLayout()
        content_h.setSpacing(20)

        # Первая фотка СЛЕВА
        lbl_img = QLabel()
        lbl_img.setPixmap(load_b64_pixmap(EMBEDDED_GUIDE_IMG_B64))
        lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_h.addWidget(lbl_img)

        guide_html = (
            "<h2 style='margin-bottom: 6px;'>Как пользоваться программой</h2>"
            "<p>Всё максимально просто: закидываешь сюда оригинал стрипа и текстовик с переводом "
            "(можно через кнопки сверху, а можно просто перетащить файлы мышкой прямо в окно).</p>"
            "<p><b>Как оформлять .txt файл:</b><br>"
            "— Если строчка начинается с тире (<code>- Привет!</code>), прога понимает, что это обычная реплика для бабла, "
            "и ставит наш шрифт <b>Peanuts by me</b>.<br>"
            "— Если строчка без тире (например, <code>ХАХАХА!</code> или <code>ААЙ!</code>), то это крик или звук на фоне. "
            "Он ставится крупным шрифтом <b>MP Manga Font</b> с прозрачной серединой и чёрной обводкой (переключить обводку и сплошную заливку можно кнопкой <b>«Shadow / Обычный»</b>).<br>"
            "— Даты стрипов и сноски через звёздочку <code>*</code> можешь не удалять, прога сама их пропустит.</p>"
            "<p><b>Если надо что-то подправить руками:</b><br>"
            "• Мышкой просто перетаскивай текст куда нужно. Двойной клик по тексту — дописать или исправить буквы.<br>"
            "• Когда кликаешь на фразу, появляется рамка: тяни за <b>синий квадратик</b> сбоку, чтобы сузить или расширить столбик текста "
            "(длинные слова сами перенесутся по слогам), или за <b>зелёный квадратик</b> в углу, чтобы изменить размер шрифта.<br>"
            "• Если где-то от оригинала осталась лишняя точка или штрих — просто зажми <b>правую кнопку мыши</b> и сотри её как ластиком.<br>"
            "• Если накосячил, жми <b>Ctrl+Z</b> (или кнопку «Отменить»), всё вернётся назад.</p>"
        )
        lbl_txt = QLabel(guide_html)
        lbl_txt.setWordWrap(True)
        lbl_txt.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        content_h.addWidget(lbl_txt, stretch=1)

        main_v.addLayout(content_h)

        btn_close = QPushButton("Понятно!")
        btn_close.setFixedWidth(180)
        btn_close.clicked.connect(dlg.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        main_v.addLayout(btn_row)

        dlg.exec()

    def show_about(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("О нас — RUS PEANUTS")
        dlg.setMinimumWidth(640)
        dlg.setStyleSheet("QDialog { background-color: white; } QLabel { color: #111; font-size: 13px; }")

        main_v = QVBoxLayout(dlg)
        content_h = QHBoxLayout()
        content_h.setSpacing(20)

        about_html = (
            "<h2 style='margin-bottom: 6px;'>RUS PEANUTS!</h2>"
            "<p>Эта прога сделана специально для нашего проекта, чтобы мы больше не тратили кучу времени "
            "на однообразную ручную чистку каждого бабла и подгонку каждой строчки в фотошопе.</p>"
            "<p><b>Наши площадки:</b><br>"
            "• Паблик ВК: <b>vk.com/ruspeanuts</b><br>"
            "• Сайт-архив: <b>ruspeanuts.com</b></p>"
            "<p>Делаем переводы с душой и любовью к Чарли Брауну, Снупи и всей компании!</p>"
        )
        lbl_txt = QLabel(about_html)
        lbl_txt.setWordWrap(True)
        lbl_txt.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        content_h.addWidget(lbl_txt, stretch=1)

        # Вторая фотка СПРАВА
        lbl_img = QLabel()
        lbl_img.setPixmap(load_b64_pixmap(EMBEDDED_ABOUT_IMG_B64))
        lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_h.addWidget(lbl_img)

        main_v.addLayout(content_h)

        btn_close = QPushButton("Закрыть")
        btn_close.setFixedWidth(140)
        btn_close.clicked.connect(dlg.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        main_v.addLayout(btn_row)

        dlg.exec()

    def toggle_selected_outline(self):
        active = self.get_active_blocks()
        if active:
            self.push_undo_state()
            for item in active:
                item.toggle_outline()

    def open_arch_dialog(self):
        active = self.get_active_blocks()
        if not active:
            QMessageBox.information(self, "Изгиб текста", "Сначала кликни на нужный текст на стрипе, чтобы выделить его.")
            return

        self.push_undo_state()
        dlg = QDialog(self)
        dlg.setWindowTitle("Изгиб текста")
        dlg.setMinimumWidth(360)
        v = QVBoxLayout(dlg)

        init_val = getattr(active[0], "arch_amount", 0)
        lbl = QLabel(f"Сила изгиба: {init_val} (плюс — дуга вверх, минус — дуга вниз)")
        v.addWidget(lbl)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(-120)
        slider.setMaximum(120)
        slider.setValue(init_val)
        v.addWidget(slider)

        def on_val_change(val):
            lbl.setText(f"Сила изгиба: {val} (плюс — дуга вверх, минус — дуга вниз)")
            for item in active:
                item.set_arch(val)

        slider.valueChanged.connect(on_val_change)

        btns = QHBoxLayout()
        btn_reset = QPushButton("Сбросить (0)")
        btn_reset.clicked.connect(lambda: slider.setValue(0))
        btn_ok = QPushButton("Готово")
        btn_ok.clicked.connect(dlg.accept)
        btns.addWidget(btn_reset)
        btns.addStretch()
        btns.addWidget(btn_ok)
        v.addLayout(btns)

        dlg.exec()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            active = self.get_active_blocks()
            if active:
                self.push_undo_state()
                for item in active:
                    self.scene.removeItem(item)
                    if item in self.text_blocks:
                        self.text_blocks.remove(item)
            event.accept()
            return
        super().keyPressEvent(event)

    def paint_white_spot(self, x, y, radius=12):
        if self.current_cv_img is None or self.pixmap_item is None:
            return
        h, w, _ = self.current_cv_img.shape
        if 0 <= x < w and 0 <= y < h:
            cv2.circle(self.current_cv_img, (x, y), radius, (255, 255, 255), -1)
            self.cleaned_pixmap = self.cv2_to_qpixmap(self.current_cv_img)
            self.pixmap_item.setPixmap(self.cleaned_pixmap)

    def get_active_blocks(self):
        return [it for it in self.scene.selectedItems() if isinstance(it, ComicText)]

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            ext = os.path.splitext(path)[1].lower()
            if ext in [".png", ".jpg", ".jpeg"]:
                self.load_image(path)
            elif ext == ".txt":
                self.load_txt(path)

    def open_image_dialog(self):
        f, _ = QFileDialog.getOpenFileName(self, "Выбрать стрип", "", "Изображения (*.png *.jpg *.jpeg)")
        if f:
            self.load_image(f)

    def open_txt_dialog(self):
        f, _ = QFileDialog.getOpenFileName(self, "Выбрать перевод", "", "Текст (*.txt)")
        if f:
            self.load_txt(f)

    def cv2_to_qpixmap(self, cv_img):
        rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimg.copy())

    def load_image(self, path):
        orig_img, e_mask, boxes, sfx_boxes = analyze_strip_universal(path)
        if orig_img is None:
            QMessageBox.critical(self, "Ошибка", "Не удалось открыть изображение.")
            return

        self.orig_cv_img = orig_img
        self.erase_mask = e_mask
        self.detected_boxes = boxes
        self.detected_sfx = sfx_boxes
        self.undo_stack.clear()
        self.update_undo_button()

        if self.current_txt_path:
            self.load_txt(self.current_txt_path)
        else:
            all_to_clean = boxes + sfx_boxes
            self.current_cv_img = clean_selected_bubbles(orig_img, e_mask, all_to_clean)
            self.cleaned_pixmap = self.cv2_to_qpixmap(self.current_cv_img)
            self.scene.clear()
            self.text_blocks.clear()
            self.pixmap_item = self.scene.addPixmap(self.cleaned_pixmap)
            self.scene.setSceneRect(QRectF(self.cleaned_pixmap.rect()))
            self.lbl_status.setText(
                f"Стрип очищен! Найдено баблов: {len(boxes)}, звуков/SFX: {len(sfx_boxes)}."
            )

    def load_txt(self, path):
        self.current_txt_path = path
        raw_lines = None
        for enc in ["utf-8", "windows-1251", "cp1251"]:
            try:
                with open(path, "r", encoding=enc) as f:
                    raw_lines = f.readlines()
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if not raw_lines:
            return

        parsed = []
        for line in raw_lines:
            s = line.strip()
            if not s or re.match(r"^\d{4}-\d{2}-\d{2}", s) or s.startswith("(") or s.startswith("*"):
                continue
            if s.startswith("-"):
                parsed.append({"text": s.lstrip("- ").strip(), "is_bubble": True})
            else:
                parsed.append({"text": s, "is_bubble": False})

        if self.orig_cv_img is not None:
            self.push_undo_state()
            all_to_clean = self.detected_boxes + self.detected_sfx
            self.current_cv_img = clean_selected_bubbles(self.orig_cv_img, self.erase_mask, all_to_clean)
            self.cleaned_pixmap = self.cv2_to_qpixmap(self.current_cv_img)
            self.scene.clear()
            self.text_blocks.clear()
            self.pixmap_item = self.scene.addPixmap(self.cleaned_pixmap)
            self.scene.setSceneRect(QRectF(self.cleaned_pixmap.rect()))

        bubble_idx = 0
        sfx_idx = 0
        for idx, item in enumerate(parsed):
            if item["is_bubble"] and bubble_idx < len(self.detected_boxes):
                box = self.detected_boxes[bubble_idx]
                bubble_idx += 1
            elif not item["is_bubble"] and sfx_idx < len(self.detected_sfx):
                box = self.detected_sfx[sfx_idx]
                sfx_idx += 1
            else:
                box = (80 + sfx_idx * 180, 45, 160, 70)
                sfx_idx += 1

            block = ComicText(
                text=item["text"],
                is_bubble=item["is_bubble"],
                box=box,
                main_win=self
            )
            self.scene.addItem(block)
            self.text_blocks.append(block)

        self.lbl_status.setText(
            f"Найдено баблов: {len(self.detected_boxes)}, SFX: {len(self.detected_sfx)} | Расставлено фраз: {len(parsed)}."
        )

    def adjust_font(self, delta):
        active = self.get_active_blocks()
        if active:
            self.push_undo_state()
            for item in active:
                item.change_size(delta)

    def adjust_width(self, delta):
        active = self.get_active_blocks()
        if active:
            self.push_undo_state()
            for item in active:
                item.change_width(delta)

    def toggle_italic(self):
        active = self.get_active_blocks()
        if active:
            self.push_undo_state()
            for item in active:
                item.toggle_italic()

    def adjust_stretch(self, delta):
        active = self.get_active_blocks()
        if active:
            self.push_undo_state()
            for item in active:
                item.change_stretch(delta)

    def adjust_weight(self, delta):
        active = self.get_active_blocks()
        if active:
            self.push_undo_state()
            for item in active:
                item.change_weight(delta)

    def save_result(self):
        if not self.cleaned_pixmap:
            return
        self.scene.clearSelection()
        out, _ = QFileDialog.getSaveFileName(self, "Сохранить", "strip_done.png", "PNG (*.png)")
        if out:
            img = QImage(self.cleaned_pixmap.size(), QImage.Format.Format_ARGB32)
            img.fill(Qt.GlobalColor.white)
            painter = QPainter(img)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            self.scene.render(painter)
            painter.end()
            img.save(out)
            QMessageBox.information(self, "Готово", "Стрип сохранен!")


if __name__ == "__main__":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ruspeanuts.autotypesetter.v7")
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(load_b64_pixmap(EMBEDDED_APP_ICON_B64)))
    init_fonts()
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
