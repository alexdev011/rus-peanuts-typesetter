"""Экспорт в PSD с настоящими текстовыми слоями: PSD собирает сам Фотошоп.

Программа готовит папку задания (фон, оригинал, сценарий JSX с данными блоков)
и просит Фотошоп выполнить сценарий через COM. Если Фотошоп недоступен,
сценарий можно запустить вручную: Файл -> Сценарии -> Обзор.

Слои PSD (снизу вверх): «Фон» — очищенный стрип, «Оригинал» — скрытый английский
оригинал для сверки, затем по текстовому слою на каждый Текстовый блок.
Изгиб передаётся деформацией «Дуга», Жирность — обводкой слоя: в Фотошопе
это выглядит близко к программе, но не пиксель в пиксель.
"""
import json
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2

from rus_peanuts.typesetting.document import Document, TextBlock

ORIGINAL_LAYER = "Оригинал"
LOG_OK = "OK"


@dataclass(frozen=True)
class TextLayer:
    """Параметры текстового слоя Фотошопа (в пикселях стрипа)."""
    contents: str     # строки через \r — переносы ровно как в программе
    font: str         # PostScript-имя
    size: float
    leading: float
    x: float          # опорная точка: центр базовой линии первой строки
    y: float
    hscale: int       # растяжение, %
    italic: bool
    stroke: int       # обводка слоя, px (0 — нет)
    warp: int         # деформация «Дуга», % (0 — нет)


@dataclass(frozen=True)
class PsdJob:
    psd_path: Path
    workdir: Path
    script: Path
    log: Path


def text_layer(block: TextBlock, typography) -> TextLayer:
    st = typography.set_text(block)
    first = st.lines[0] if st.lines else None
    warp = 0
    if block.arch:
        # Изгиб в программе: середина строки выше краёв на arch пикселей.
        # «Дуга» Фотошопа задаётся в процентах — от половины ширины самой длинной строки.
        half = max([line.width for line in st.lines] + [2.0]) / 2
        warp = max(-100, min(100, round(100 * block.arch / half)))
    stroke = max(1, round(typography.bold_pen_width(block) / 2)) if block.bold > 0 else 0
    return TextLayer(
        contents="\r".join(line.text for line in st.lines),
        font=typography.fonts.postscript(block.is_reply, block.shadow),
        size=round(st.size_px, 2),
        leading=round(st.leading_px, 2),
        x=round(block.x + (first.center_x if first else 0), 2),
        y=round(block.y + (first.baseline_y if first else 0), 2),
        hscale=int(block.stretch),
        italic=bool(block.italic),
        stroke=stroke,
        warp=warp,
    )


def _write_png(bgr, path: Path) -> None:
    ok, buf = cv2.imencode(".png", bgr)
    if not ok:
        raise OSError(f"не удалось записать {path}")
    buf.tofile(str(path))


def prepare(doc: Document, typography, psd_path, workdir=None, with_original: bool = True) -> PsdJob:
    """Готовит папку задания для Фотошопа и возвращает его описание."""
    if doc.image is None:
        raise ValueError("в Документе нет стрипа")
    psd_path = Path(psd_path).resolve()
    workdir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="rus_peanuts_psd_"))
    workdir.mkdir(parents=True, exist_ok=True)
    background = workdir / "background.png"
    _write_png(doc.image, background)
    original = None
    if with_original and doc.original is not None:
        original = workdir / "original.png"
        _write_png(doc.original, original)
    log = workdir / "photoshop.log"
    if log.exists():
        log.unlink()

    data = {
        "background": background.resolve().as_posix(),
        "original": original.resolve().as_posix() if original else None,
        "originalName": ORIGINAL_LAYER,
        "output": psd_path.as_posix(),
        "log": log.resolve().as_posix(),
        "layers": [asdict(text_layer(b, typography)) for b in doc.blocks],
    }
    script = workdir / "build_psd.jsx"
    script.write_text(JSX_TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=True, indent=1)),
                      encoding="utf-8-sig")
    return PsdJob(psd_path=psd_path, workdir=workdir, script=script, log=log)


def photoshop_command(job: PsdJob) -> list[str]:
    """Команда, которая запускает сценарий в Фотошопе через COM и ждёт его окончания."""
    script = str(job.script.resolve()).replace("'", "''")
    return [
        "powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
        "$ErrorActionPreference = 'Stop'; "
        "$ps = New-Object -ComObject Photoshop.Application; "
        f"$null = $ps.DoJavaScriptFile('{script}')",
    ]


def result(job: PsdJob) -> tuple[bool, str]:
    """Итог по журналу сценария: (успех, сообщение)."""
    if not job.log.exists():
        return False, "Фотошоп не выполнил сценарий (нет журнала)."
    text = job.log.read_text(encoding="utf-8", errors="replace").strip()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    warnings = [ln for ln in lines if ln.startswith("WARN")]
    if lines and lines[-1] == LOG_OK and job.psd_path.exists():
        return True, "\n".join(warnings)
    return False, "\n".join(lines) or "Фотошоп завершился без результата."


def run(job: PsdJob, timeout: float = 600) -> tuple[bool, str]:
    """Запускает сценарий в Фотошопе и ждёт (для тестов и командной строки)."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(photoshop_command(job), capture_output=True, text=True,
                              timeout=timeout, creationflags=flags)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"Не удалось запустить Фотошоп: {e}"
    ok, message = result(job)
    if not ok and proc.returncode != 0 and not job.log.exists():
        message = (proc.stderr or proc.stdout or message).strip()
    return ok, message


def export_psd(doc: Document, typography, psd_path, timeout: float = 600) -> tuple[bool, str, PsdJob]:
    job = prepare(doc, typography, psd_path)
    ok, message = run(job, timeout)
    return ok, message, job


# Сценарий для Фотошопа (ExtendScript, ES3). __DATA__ заменяется данными задания.
JSX_TEMPLATE = r'''// Сгенерировано RUS PEANUTS: собирает PSD с настоящими текстовыми слоями.
// Можно запустить и вручную: Фотошоп -> Файл -> Сценарии -> Обзор...
// Совместимо с Photoshop CC 2019+ (ExtendScript, ES3).
#target photoshop
(function () {
    var DATA = __DATA__;

    function log(message) {
        var f = new File(DATA.log);
        f.encoding = "UTF-8";
        f.open("a");
        f.writeln(message);
        f.close();
    }

    function black() {
        var c = new SolidColor();
        c.rgb.red = 0;
        c.rgb.green = 0;
        c.rgb.blue = 0;
        return c;
    }

    // Обводка слоя (Жирность): стиль слоя «Выполнить обводку», снаружи, чёрная
    function addStroke(sizePx) {
        var desc = new ActionDescriptor();
        var ref = new ActionReference();
        ref.putProperty(charIDToTypeID("Prpr"), charIDToTypeID("Lefx"));
        ref.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
        desc.putReference(charIDToTypeID("null"), ref);
        var fx = new ActionDescriptor();
        fx.putUnitDouble(charIDToTypeID("Scl "), charIDToTypeID("#Prc"), 100.0);
        var stroke = new ActionDescriptor();
        stroke.putBoolean(charIDToTypeID("enab"), true);
        stroke.putEnumerated(charIDToTypeID("Styl"), charIDToTypeID("FStl"), charIDToTypeID("OutF"));
        stroke.putEnumerated(charIDToTypeID("PntT"), charIDToTypeID("FrFl"), charIDToTypeID("SClr"));
        stroke.putEnumerated(charIDToTypeID("Md  "), charIDToTypeID("BlnM"), charIDToTypeID("Nrml"));
        stroke.putUnitDouble(charIDToTypeID("Opct"), charIDToTypeID("#Prc"), 100.0);
        stroke.putUnitDouble(charIDToTypeID("Sz  "), charIDToTypeID("#Pxl"), sizePx);
        var color = new ActionDescriptor();
        color.putDouble(charIDToTypeID("Rd  "), 0);
        color.putDouble(charIDToTypeID("Grn "), 0);
        color.putDouble(charIDToTypeID("Bl  "), 0);
        stroke.putObject(charIDToTypeID("Clr "), charIDToTypeID("RGBC"), color);
        fx.putObject(charIDToTypeID("FrFX"), charIDToTypeID("FrFX"), stroke);
        desc.putObject(charIDToTypeID("T   "), charIDToTypeID("Lefx"), fx);
        executeAction(charIDToTypeID("setd"), desc, DialogModes.NO);
    }

    function addText(doc, spec) {
        var layer = doc.artLayers.add();
        layer.kind = LayerKind.TEXT;
        var t = layer.textItem;
        t.contents = spec.contents;
        try {
            t.font = spec.font;
        } catch (e) {
            log("WARN: font " + spec.font + ": " + e);
        }
        t.size = spec.size;
        t.useAutoLeading = false;
        t.leading = spec.leading;
        t.color = black();
        t.justification = Justification.CENTER;
        t.horizontalScale = spec.hscale;
        t.fauxItalic = spec.italic;
        t.antiAliasMethod = AntiAlias.SMOOTH;
        if (spec.warp !== 0) {
            t.warpStyle = WarpStyle.ARC;
            t.warpDirection = Direction.HORIZONTAL;
            t.warpBend = spec.warp;
        }
        t.position = [spec.x, spec.y];
        if (spec.stroke > 0) {
            addStroke(spec.stroke);
        }
        return layer;
    }

    var prefs = app.preferences;
    var oldRuler = prefs.rulerUnits;
    var oldType = prefs.typeUnits;
    var oldDialogs = app.displayDialogs;
    prefs.rulerUnits = Units.PIXELS;
    prefs.typeUnits = TypeUnits.PIXELS;
    app.displayDialogs = DialogModes.NO;
    var doc = null;
    try {
        doc = app.open(new File(DATA.background));
        if (DATA.original) {
            var od = app.open(new File(DATA.original));
            var copy = od.artLayers[0].duplicate(doc, ElementPlacement.PLACEATBEGINNING);
            od.close(SaveOptions.DONOTSAVECHANGES);
            app.activeDocument = doc;
            copy.name = DATA.originalName;
            copy.visible = false;
            doc.activeLayer = copy;
        }
        for (var i = 0; i < DATA.layers.length; i++) {
            addText(doc, DATA.layers[i]);
        }
        var opts = new PhotoshopSaveOptions();
        opts.layers = true;
        doc.saveAs(new File(DATA.output), opts, true, Extension.LOWERCASE);
        doc.close(SaveOptions.DONOTSAVECHANGES);
        doc = null;
        log("OK");
    } catch (e) {
        log("ERROR: " + e + (e.line ? " (line " + e.line + ")" : ""));
        if (doc) {
            try {
                doc.close(SaveOptions.DONOTSAVECHANGES);
            } catch (e2) {}
        }
    } finally {
        prefs.rulerUnits = oldRuler;
        prefs.typeUnits = oldType;
        app.displayDialogs = oldDialogs;
    }
})();
'''
