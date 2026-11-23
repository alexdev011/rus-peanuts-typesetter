"""Главное окно: вкладка вёрстки (холст + панель кнопок) и вкладка Multi tool."""
import os

from qtpy.QtCore import QProcess, QRectF, Qt, QUrl
from qtpy.QtGui import QDesktopServices, QFont, QIcon, QKeySequence, QPainter, QShortcut
from qtpy.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QFileDialog, QGraphicsScene, QHBoxLayout, QInputDialog, QLabel,
    QListWidget, QMainWindow, QMenu, QMessageBox, QPushButton, QSizePolicy, QSpinBox, QSplitter, QTabWidget,
    QVBoxLayout, QWidget,
)

from rus_peanuts import publishing
from rus_peanuts.export import psd
from rus_peanuts.export.png import export_png
from rus_peanuts.typesetting import analysis, project, translation
from rus_peanuts.typesetting.batch import IMAGE_EXTENSIONS, Batch, strip_date
from rus_peanuts.typesetting.document import BLACK, WHITE, Document, TextBlock
from rus_peanuts.typesetting.fonts import FONT_EXTENSIONS
from rus_peanuts.typesetting.layout import Typography

from . import dialogs, embedded
from .icons import cursor_icon
from rus_peanuts.typesetting.graphics import to_qpixmap

from .block_item import BlockItem
from .canvas import DEFAULT_BRUSH, StripCanvasView
from .multitool_tab import MultiToolQtTab
from .qt_setup import add_action


cv2_to_qpixmap = to_qpixmap
RECENT_FONTS = 5  # сколько недавних шрифтов показывать вверху списка


def result_path(filename: str = "") -> str:
    """Путь в папке result — той же, куда пишет Multi tool. Окна сохранения открываются в ней."""
    folder = os.path.abspath(publishing.RESULT_DIR)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, filename) if filename else folder


class MainWindow(QMainWindow):
    def __init__(self, typography: Typography):
        super().__init__()
        self.setWindowTitle("RUS PEANUTS — Auto-Typesetter")
        self.resize(1320, 860)
        self.setAcceptDrops(True)

        self.typography = typography
        self.document = Document(typography)
        self.current_txt_path = None            # Файл перевода
        self.strip_name = "strip"
        self.strip_path = None                  # Оригинал, открытый одним файлом
        self.batch: Batch | None = None         # Пачка, если открыта папка
        self.batch_index = -1
        self.batch_problems = None
        self.psd_process = None
        self.pick_note = ""                     # что не так с выбором Перевода для одного стрипа
        self.cleaned_pixmap = None
        self.orig_qpixmap = None
        self.pixmap_item = None
        self.items: list[BlockItem] = []
        self.recent_fonts: list[str] = []
        self._syncing = False

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

        # Панель: файлы, отмена, вид выделенного текста (Шрифт и стиль), оригинал, справка
        bar = QHBoxLayout()
        self.btn_img = self._button("1. Стрип", None, "Открыть один стрип или папку со стрипами (Пачку)")
        img_menu = QMenu(self.btn_img)
        img_menu.addAction("Файл…", self.open_image_dialog)
        img_menu.addAction("Папка…", self.open_folder_dialog)
        self.btn_img.setMenu(img_menu)
        self.btn_txt = self._button("2. Перевод", self.open_txt_dialog, "Загрузить перевод (.txt)")
        self.btn_undo = self._button("↩ Отменить", self.undo_action, "Отменить последнее действие (Ctrl+Z)")
        self.btn_undo.setEnabled(False)
        for w in (self.btn_img, self.btn_txt, self.btn_undo):
            bar.addWidget(w)
        bar.addSpacing(16)

        # Кегль и ширину колонки меняют маркеры на рамке блока (зелёный и синий квадратики)
        self.spin_stretch = self._spin(50, 400, 10, " %", self.set_stretch, "Растяжение шрифта по ширине")
        self.spin_bold = self._spin(0, 10, 1, "", self.set_bold, "Жирность: 0 — обычный, дальше толще")
        self.btn_italic = self._button("Курсив", self.set_italic, "Курсив", checkable=True)
        self.btn_arch = self._button("Изгиб", self.open_arch_dialog, "Изогнуть выделенный текст дугой вверх или вниз")
        self.combo_font = QComboBox()
        self.combo_font.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.combo_font.setMinimumContentsLength(18)
        self.combo_font.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_font.setMaxVisibleItems(25)
        self.combo_font.view().setMinimumWidth(320)  # имена шрифтов в списке — своим шрифтом, они шире
        self.combo_font.setToolTip("Шрифт выделенного текста. Свои шрифты — меню «Шрифты»")
        self.combo_font.activated.connect(self._font_chosen)
        bar.addWidget(self.combo_font)
        bar.addSpacing(6)
        bar.addWidget(QLabel("Растяг"))
        bar.addWidget(self.spin_stretch)
        bar.addSpacing(6)
        bar.addWidget(QLabel("Жирность"))
        bar.addWidget(self.spin_bold)
        bar.addSpacing(6)
        for w in (self.btn_italic, self.btn_arch):
            bar.addWidget(w)
        bar.addStretch()

        self.btn_orig = self._button("Показать оригинал", self.toggle_original, "Сверить с английским оригиналом",
                                     checkable=True)
        self.btn_guide = self._button("Руководство", self.show_guide)
        bar.addWidget(self.btn_orig)
        bar.addWidget(self.btn_guide)
        ts_layout.addLayout(bar)

        # Второй ряд: инструмент (Курсор или Карандаш), цвет и толщина Карандаша, строка состояния
        tools = QHBoxLayout()
        self.btn_cursor = self._button("Курсор", None, "Выделять и двигать текст (Esc)", checkable=True)
        self.btn_cursor.setIcon(cursor_icon())
        self.btn_pencil = self._button(
            "✎ Карандаш", None,
            "Закрашивать стрип левой кнопкой мыши. Вернуться к выделению текста — «Курсор» или Esc.\n"
            "Правая кнопка мыши всегда стирает белым — и без Карандаша.", checkable=True)
        self.tool_buttons = QButtonGroup(self)
        self.tool_buttons.addButton(self.btn_cursor)
        self.tool_buttons.addButton(self.btn_pencil)
        self.btn_cursor.setChecked(True)
        self.btn_pencil.toggled.connect(self.toggle_pencil)
        self.btn_white = self._button("Белый", lambda *_: self.set_pencil_color(WHITE), "Карандаш белым", checkable=True)
        self.btn_black = self._button("Чёрный", lambda *_: self.set_pencil_color(BLACK), "Карандаш чёрным", checkable=True)
        self.pencil_colors = QButtonGroup(self)
        self.pencil_colors.addButton(self.btn_white)
        self.pencil_colors.addButton(self.btn_black)
        self.btn_white.setChecked(True)
        self.spin_brush = self._spin(2, 200, 2, " px", self.set_brush_size, "Толщина Карандаша и ластика")
        for w in (self.btn_cursor, self.btn_pencil, self.btn_white, self.btn_black, QLabel("Толщина"),
                  self.spin_brush):
            tools.addWidget(w)
        tools.addSpacing(16)
        self.lbl_status = QLabel("Добро Пожаловать!")
        self.lbl_status.setStyleSheet("font-weight: bold; font-size: 12px;")
        # длинное сообщение обрезается, а не раздвигает окно
        self.lbl_status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        tools.addWidget(self.lbl_status, stretch=1)
        ts_layout.addLayout(tools)

        self.scene = QGraphicsScene(self)
        self.scene.selectionChanged.connect(self.sync_style_controls)
        self.view = StripCanvasView(self.scene, self)

        # Пачка: список стрипов слева от холста (виден, только когда открыта папка)
        self.batch_panel = QWidget()
        panel = QVBoxLayout(self.batch_panel)
        panel.setContentsMargins(0, 0, 0, 0)
        nav = QHBoxLayout()
        self.btn_prev = self._button("◀", lambda: self.step_strip(-1), "Предыдущий стрип (Ctrl+PgUp)")
        self.btn_next = self._button("▶", lambda: self.step_strip(1), "Следующий стрип (Ctrl+PgDown)")
        self.lbl_batch = QLabel()
        nav.addWidget(self.btn_prev)
        nav.addWidget(self.lbl_batch, stretch=1)
        nav.addWidget(self.btn_next)
        panel.addLayout(nav)
        self.list_strips = QListWidget()
        self.list_strips.setToolTip("● — есть несохранённые правки, ✓ — сохранён")
        self.list_strips.currentRowChanged.connect(self.show_strip)
        panel.addWidget(self.list_strips)
        self.batch_panel.setMinimumWidth(190)
        self.batch_panel.hide()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.batch_panel)
        splitter.addWidget(self.view)
        splitter.setStretchFactor(1, 1)
        splitter.setChildrenCollapsible(False)
        ts_layout.addWidget(splitter, stretch=1)
        self.spin_brush.setValue(DEFAULT_BRUSH)

        self.tab_multitool = MultiToolQtTab(self)
        self.tabs.addTab(self.tab_typesetter, "1. RUS PEANUTS — Auto-Typesetter")
        self.tabs.addTab(self.tab_multitool, "2. Multi tool for Pinats by Alimtair")

        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self.undo_action)
        QShortcut(QKeySequence("Ctrl+PgDown"), self).activated.connect(lambda: self.step_strip(1))
        QShortcut(QKeySequence("Ctrl+PgUp"), self).activated.connect(lambda: self.step_strip(-1))
        self.init_menus()
        self.refresh_font_list()

    def _button(self, text, slot, tip=None, checkable=False) -> QPushButton:
        btn = QPushButton(text)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setCheckable(checkable)
        if tip:
            btn.setToolTip(tip)
        if slot:
            btn.clicked.connect(slot)
        return btn

    def _spin(self, low, high, step, suffix, slot, tip) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setSingleStep(step)
        spin.setSuffix(suffix)
        spin.setToolTip(tip)
        spin.setKeyboardTracking(False)  # число применяется по Enter, а не на каждую цифру
        spin.valueChanged.connect(slot)
        return spin

    def init_menus(self):
        """Меню: файлы и экспорт, масштаб холста, справка."""
        menu = self.menuBar().addMenu("Файл")
        menu.addAction("Открыть стрип…", self.open_image_dialog)
        menu.addAction("Открыть папку стрипов (Пачку)…", self.open_folder_dialog)
        menu.addAction("Загрузить файл перевода (.txt)…", self.open_txt_dialog)
        menu.addSeparator()
        self.act_open_project = add_action(menu, "Открыть проект…", self.open_project_dialog, "Ctrl+O")
        self.act_save_project = add_action(menu, "Сохранить проект…", self.save_project, "Ctrl+S")
        menu.addSeparator()
        self.act_save_png = add_action(menu, "Сохранить PNG…", self.save_result, "Ctrl+Shift+S")
        self.act_export_psd = menu.addAction("Экспорт в PSD (через Фотошоп)…", self.export_psd)
        self.act_export_psd.setStatusTip("PSD с настоящими текстовыми слоями — его соберёт Фотошоп")
        menu.addSeparator()
        self.act_save_all = menu.addAction("Сохранить всю Пачку (PNG и проекты)…", self.save_all)
        self.act_save_all.setEnabled(False)

        view = self.menuBar().addMenu("Вид")
        add_action(view, "Вписать стрип в окно", self.view.fit, "Ctrl+0")
        add_action(view, "Крупнее", lambda: self.view.zoom(1.25), "Ctrl+=")
        add_action(view, "Мельче", lambda: self.view.zoom(0.8), "Ctrl+-")

        fonts_menu = self.menuBar().addMenu("Шрифты")
        self.act_add_fonts = fonts_menu.addAction("Добавить шрифты…", self.add_fonts_dialog)
        fonts_menu.addAction("Открыть папку шрифтов", self.open_fonts_folder)

        help_menu = self.menuBar().addMenu("Справка")
        help_menu.addAction("Руководство", self.show_guide)
        help_menu.addAction("О нас", self.show_about)

    def init_fixed_logo(self):
        pix_logo = embedded.pixmap(embedded.EMBEDDED_LOGO_B64)
        if not pix_logo.isNull():
            self.lbl_logo.setPixmap(pix_logo)
        pix_icon = embedded.pixmap(embedded.EMBEDDED_APP_ICON_B64)
        if not pix_icon.isNull():
            self.setWindowIcon(QIcon(pix_icon))

    # ------------------------------------------------ Документ <-> холст

    def rebuild_scene(self, selected=()):
        """Перерисовать холст целиком по Документу."""
        doc = self.document
        self.scene.clear()
        self.items = []
        self.pixmap_item = None
        self.cleaned_pixmap = None
        if doc.image is not None:
            self.cleaned_pixmap = cv2_to_qpixmap(doc.image)
            self.pixmap_item = self.scene.addPixmap(self.cleaned_pixmap)
            self.scene.setSceneRect(QRectF(self.cleaned_pixmap.rect()))
        for i, block in enumerate(doc.blocks):
            item = BlockItem(block, self)
            self.scene.addItem(item)
            item.setSelected(i in selected)
            self.items.append(item)
        self.update_undo_button()
        self.sync_style_controls()
        if self.view.fit_mode:
            self.view.fit()

    def selected_items(self) -> list[BlockItem]:
        return [it for it in self.scene.selectedItems() if isinstance(it, BlockItem)]

    def checkpoint(self):
        selected = [i for i, it in enumerate(self.items) if it.isSelected()]
        self.document.checkpoint(selected)
        self.update_undo_button()
        self.refresh_strip_list()

    def drop_checkpoint(self):
        self.document.drop_checkpoint()
        self.update_undo_button()
        self.refresh_strip_list()

    def update_undo_button(self):
        self.btn_undo.setEnabled(self.document.can_undo)

    def undo_action(self):
        selected = self.document.undo()
        if selected is None:
            return
        self.rebuild_scene(selected)
        self.refresh_strip_list()
        self.lbl_status.setText("Действие отменено!")

    # ---------------------------------------------------- загрузка файлов

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            ext = os.path.splitext(path)[1].lower()
            if os.path.isdir(path):
                self.open_folder(path)
            elif ext in IMAGE_EXTENSIONS:
                self.load_image(path)
            elif ext == ".txt":
                self.load_txt(path)
            elif ext == project.EXTENSION:
                self.load_project(path)
            elif ext in FONT_EXTENSIONS:
                self.add_fonts([path])

    def open_image_dialog(self):
        f, _ = QFileDialog.getOpenFileName(self, "Выбрать стрип", "", "Изображения (*.png *.jpg *.jpeg)")
        if f:
            self.load_image(f)

    def open_txt_dialog(self):
        f, _ = QFileDialog.getOpenFileName(self, "Выбрать файл перевода", "", "Текст (*.txt)")
        if f:
            self.load_txt(f)

    def open_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Папка со стрипами")
        if folder:
            self.open_folder(folder)

    def _pick_lines(self, tf, date):
        """Перевод для одного стрипа из Файла перевода: по дате, а без даты — спросить.
        Заметку для строки состояния кладёт в `self.pick_note`."""
        self.pick_note = ""
        if tf is None:
            return None
        if tf.undated is not None or (date is None and len(tf.dates) == 1):
            return tf.only()
        if date is None:
            date, ok = QInputDialog.getItem(self, "Какой Перевод взять",
                                            "В имени стрипа нет даты. Выберите дату из файла перевода:",
                                            tf.dates, 0, False)
            if not ok or not date:
                return None
        lines = tf.for_date(date)
        if lines is None and len(tf.dates) == 1:
            # один стрип и один Перевод — путать нечего, но дата не сходится: возможно, опечатка
            self.pick_note = f"В файле перевода дата {tf.dates[0]}, а у стрипа {date} — взят единственный Перевод. "
            return tf.only()
        if lines is None:
            self.pick_note = f"В файле перевода нет Перевода на {date}. "
        return lines

    def load_image(self, path):
        if not self._leave_batch():
            return
        img = analysis.load_image(path)
        if img is None:
            QMessageBox.critical(self, "Ошибка", "Не удалось открыть изображение.")
            return
        # Перевод перечитывается с диска: если файл поправили, подхватятся изменения
        tf = translation.read(self.current_txt_path) if self.current_txt_path else None
        self.document = Document(self.typography)
        self.document.open_strip(img, self._pick_lines(tf, strip_date(path)))
        self.strip_path = path
        self.strip_name = os.path.splitext(os.path.basename(path))[0]
        self._show_document()

    def load_txt(self, path):
        tf = translation.read(path)
        if tf is None:
            QMessageBox.warning(self, "Перевод", "Не удалось прочитать файл перевода или он пустой.")
            return
        self.current_txt_path = path
        if self.batch is not None:
            self.batch.set_translation(path)
            self.batch_problems = self.batch.problems()
            strip = self.batch.strips[self.batch_index]
            if strip.document is None:              # стрип не правили — собрать заново с новым Переводом
                self.document = self.batch.open(self.batch_index)
            else:
                self.document.set_translation(self.batch.lines_for(strip, tf) or [])
            self._show_document()
            self._report_batch_problems()
            return
        if self.document.image is None and tf.only() is None:
            self.lbl_status.setText(f"Файл перевода загружен: переводов {len(tf.dates)}. Теперь откройте стрип или папку.")
            return
        date = strip_date(self.strip_path) if self.strip_path else None
        lines = self._pick_lines(tf, date)
        if lines is None:
            if self.pick_note:
                self.lbl_status.setText(self.pick_note)
            return
        self.document.set_translation(lines)
        self.rebuild_scene()
        self._show_counts()

    def _show_document(self):
        """Показать текущий Документ с нуля: новый стрип, стрип Пачки, открытый проект."""
        if self.btn_orig.isChecked():
            self.btn_orig.setChecked(False)
            self.btn_orig.setText("Показать оригинал")
        self.orig_qpixmap = None
        self.view.fit_mode = True
        self.rebuild_scene()
        self._show_counts()
        self.refresh_strip_list()

    def _show_counts(self):
        doc = self.document
        prefix = self.pick_note if self.batch is None else ""
        if self.batch is not None:
            strip = self.batch.strips[self.batch_index]
            prefix = f"{strip.name}: "
            if strip.date is None:
                prefix += "в имени нет даты, перевода нет. "
            elif self.batch_problems and strip.name in self.batch_problems.no_translation:
                prefix += f"нет Перевода на {strip.date}. "
        if doc.lines is None:
            self.lbl_status.setText(
                prefix + f"Стрип очищен! Найдено баблов: {len(doc.bubbles)}, звуков: {len(doc.sounds)}."
            )
            return
        text = prefix + (f"Найдено баблов: {len(doc.bubbles)}, звуков: {len(doc.sounds)}"
                         f" | Расставлено фраз: {len(doc.lines)}.")
        undashed = translation.replies_without_dash(doc.lines)
        if undashed:
            names = ", ".join(f"«{ln.text[:20]}»" for ln in undashed[:2]) + (" …" if len(undashed) > 2 else "")
            text += f" Без тире до «Звуки:» — поставлены как реплики: {names}"
        self.lbl_status.setText(text)

    # ------------------------------------------------------- правка блоков

    def _edit_selected(self, change):
        items = self.selected_items()
        if items:
            self.checkpoint()
            for item in items:
                change(item.block)
                item.refresh()

    def _set_on_selected(self, attr, value, setter):
        """Задать значение выделенным блокам (без записи в историю, если менять нечего)."""
        if self._syncing:
            return
        items = self.selected_items()
        if items and any(getattr(it.block, attr) != value for it in items):
            self._edit_selected(lambda b: setter(b, value))

    def set_stretch(self, value):
        self._set_on_selected("stretch", value, TextBlock.set_stretch)

    def set_bold(self, value):
        self._set_on_selected("bold", value, TextBlock.set_bold)

    def set_italic(self, checked):
        self._set_on_selected("italic", bool(checked), TextBlock.set_italic)

    def sync_style_controls(self):
        """Шрифт, счётчики и «Курсив» показывают вид первого выделенного блока."""
        items = self.selected_items()
        self._syncing = True
        try:
            for w in (self.combo_font, self.spin_stretch, self.spin_bold, self.btn_italic, self.btn_arch):
                w.setEnabled(bool(items))
            if items:
                b = items[0].block
                self.spin_stretch.setValue(b.stretch)
                self.spin_bold.setValue(b.bold)
                self.btn_italic.setChecked(b.italic)
                index = self.combo_font.findData(b.font)
                self.combo_font.setPlaceholderText(f"нет шрифта: {b.font}")
                self.combo_font.setCurrentIndex(index)
            else:
                self.btn_italic.setChecked(False)
                self.combo_font.setPlaceholderText("Шрифт")
                self.combo_font.setCurrentIndex(-1)
        finally:
            self._syncing = False

    # ---------------------------------------------------------------- Шрифты

    def refresh_font_list(self):
        """Список шрифтов: недавние сверху, дальше весь Набор по алфавиту."""
        library = self.typography.fonts
        recent = [f for f in (library.get(ps) for ps in self.recent_fonts) if f]
        self._syncing = True
        try:
            self.combo_font.clear()
            for face in recent:
                self._add_font_item(face)
            if recent:
                self.combo_font.insertSeparator(self.combo_font.count())
            for face in library.faces:
                self._add_font_item(face)
        finally:
            self._syncing = False
        self.sync_style_controls()

    def _add_font_item(self, face):
        combo = self.combo_font
        combo.addItem(face.name, face.postscript)
        i = combo.count() - 1
        combo.setItemData(i, QFont(face.family, 11), Qt.ItemDataRole.FontRole)  # имя — своим шрифтом
        combo.setItemData(i, face.postscript, Qt.ItemDataRole.ToolTipRole)

    def _font_chosen(self, index):
        postscript = self.combo_font.itemData(index)
        if postscript:
            self.set_font(postscript)

    def set_font(self, postscript):
        if self._syncing or not self.selected_items():
            return
        self._set_on_selected("font", postscript, TextBlock.set_font)
        if postscript in self.recent_fonts:
            self.recent_fonts.remove(postscript)
        self.recent_fonts.insert(0, postscript)
        del self.recent_fonts[RECENT_FONTS:]
        self.refresh_font_list()

    def add_fonts_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Добавить шрифты", "", "Шрифты (*.ttf *.otf)")
        if files:
            self.add_fonts(files)

    def add_fonts(self, paths) -> list:
        """Копирует шрифты в папку Набора — они останутся и после перезапуска."""
        added, failed = [], []
        for path in paths:
            try:
                face = self.typography.fonts.install(path)
            except OSError as e:
                face, reason = None, str(e)
            else:
                reason = "не похоже на шрифт"
            if face:
                added.append(face)
            else:
                failed.append(f"{os.path.basename(path)}: {reason}")
        self.refresh_font_list()
        self.lbl_status.setText(f"Добавлено шрифтов: {len(added)}")
        if failed:
            QMessageBox.warning(self, "Шрифты", "Не удалось добавить:\n" + "\n".join(failed))
        return added

    def open_fonts_folder(self):
        folder = self.typography.fonts.folder
        if folder:
            os.makedirs(folder, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def open_arch_dialog(self):
        items = self.selected_items()
        if not items:
            QMessageBox.information(self, "Изгиб текста", "Сначала кликни на нужный текст на стрипе, чтобы выделить его.")
            return
        self.checkpoint()
        dialogs.arch_dialog(self, items)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.btn_pencil.isChecked():
            self.btn_cursor.setChecked(True)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Delete:
            items = self.selected_items()
            if items:
                self.checkpoint()
                self.document.remove([it.block for it in items])
                for it in items:
                    self.scene.removeItem(it)
                    self.items.remove(it)
            event.accept()
            return
        super().keyPressEvent(event)

    # -------------------------------------------------------------- Карандаш

    def toggle_pencil(self, on):
        self.view.set_pencil(on)
        if on:
            self.lbl_status.setText("Карандаш: рисуй левой кнопкой мыши. Вернуться к тексту — «Курсор» или Esc.")

    def set_pencil_color(self, color):
        self.view.set_brush(color=color)
        self.btn_pencil.setChecked(True)  # выбрал цвет — значит, хочешь рисовать

    def set_brush_size(self, size):
        self.view.set_brush(size=size)

    @property
    def can_paint(self) -> bool:
        return self.cleaned_pixmap is not None and not self.btn_orig.isChecked()

    def paint(self, x0, y0, x1, y1, radius, color):
        if self.pixmap_item is None or not self.document.paint(x0, y0, x1, y1, radius, color):
            return
        # На экране обновляется только закрашенный кусок — на больших Страницах это заметно быстрее
        h, w = self.document.image.shape[:2]
        left, top = max(0, min(x0, x1) - radius - 1), max(0, min(y0, y1) - radius - 1)
        right, bottom = min(w, max(x0, x1) + radius + 2), min(h, max(y0, y1) + radius + 2)
        painter = QPainter(self.cleaned_pixmap)
        painter.drawPixmap(left, top, cv2_to_qpixmap(self.document.image[top:bottom, left:right]))
        painter.end()
        self.pixmap_item.setPixmap(self.cleaned_pixmap)

    # ------------------------------------------------------------- прочее

    def toggle_original(self, checked):
        if self.document.original is None or not self.cleaned_pixmap:
            self.btn_orig.setChecked(False)
            return
        if checked:
            if self.orig_qpixmap is None:
                self.orig_qpixmap = cv2_to_qpixmap(self.document.original)
            self.pixmap_item.setPixmap(self.orig_qpixmap)
            for it in self.items:
                it.setVisible(False)
            self.btn_orig.setText("Вернуть результат")
        else:
            self.pixmap_item.setPixmap(self.cleaned_pixmap)
            for it in self.items:
                it.setVisible(True)
            self.btn_orig.setText("Показать оригинал")

    def show_guide(self):
        dialogs.show_guide(self)

    def show_about(self):
        dialogs.show_about(self)

    def save_result(self):
        if self.document.image is None:
            return
        self.scene.clearSelection()
        out, _ = QFileDialog.getSaveFileName(self, "Сохранить", result_path(self.strip_name + ".png"), "PNG (*.png)")
        if out:
            export_png(self.document, self.typography, out)
            self._mark_saved()
            QMessageBox.information(self, "Готово", "Стрип сохранен!")

    # ------------------------------------------------------------- проект

    def open_project_dialog(self):
        f, _ = QFileDialog.getOpenFileName(self, "Открыть проект", "", f"Проект RUS PEANUTS (*{project.EXTENSION})")
        if f:
            self.load_project(f)

    def load_project(self, path):
        if not self._leave_batch():
            return
        try:
            doc = project.load(path, self.typography)
        except (project.ProjectError, OSError) as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть проект:\n{e}")
            return
        self.document = doc
        self.current_txt_path = None  # Перевод уже внутри проекта
        self.strip_path = None
        self.strip_name = os.path.splitext(os.path.basename(path))[0]
        self._show_document()
        self.lbl_status.setText(f"Проект открыт: {os.path.basename(path)} | Текстовых блоков: {len(doc.blocks)}.")

    def save_project(self):
        if self.document.analysis is None:
            return
        out, _ = QFileDialog.getSaveFileName(self, "Сохранить проект", result_path(self.strip_name + project.EXTENSION),
                                             f"Проект RUS PEANUTS (*{project.EXTENSION})")
        if not out:
            return
        try:
            project.save(self.document, out)
        except (project.ProjectError, OSError) as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить проект:\n{e}")
            return
        self._mark_saved()
        self.lbl_status.setText(f"Проект сохранён: {os.path.basename(out)}")

    def _mark_saved(self):
        self.document.mark_saved()
        if self.batch is not None:
            self.batch.strips[self.batch_index].saved = True
        self.refresh_strip_list()

    # ---------------------------------------------------------------- Пачка

    def open_folder(self, folder):
        if not self._leave_batch():
            return
        batch = Batch(folder, self.typography, self.current_txt_path)
        if not batch.strips:
            QMessageBox.warning(self, "Пачка", "В папке нет стрипов (PNG, JPG).")
            return
        self.batch = batch
        self.batch_problems = batch.problems()
        self.batch_index = -1
        self.list_strips.blockSignals(True)
        self.list_strips.clear()
        self.list_strips.addItems([s.name for s in batch.strips])
        self.list_strips.blockSignals(False)
        self.batch_panel.show()
        self.act_save_all.setEnabled(True)
        self.list_strips.setCurrentRow(0)
        self._report_batch_problems()

    def show_strip(self, index):
        """Перейти к стрипу Пачки (правки прежнего остаются в памяти)."""
        if self.batch is None or index < 0 or index == self.batch_index:
            return
        if self.batch_index >= 0:
            self.batch.leave(self.batch_index)
        try:
            doc = self.batch.open(index)
        except OSError as e:
            QMessageBox.critical(self, "Ошибка", str(e))
            return
        strip = self.batch.strips[index]
        self.batch_index = index
        self.document = doc
        self.strip_path = str(strip.path)
        self.strip_name = strip.name
        self._show_document()

    def step_strip(self, delta):
        if self.batch is not None:
            row = max(0, min(len(self.batch.strips) - 1, self.batch_index + delta))
            self.list_strips.setCurrentRow(row)

    def refresh_strip_list(self):
        """Подписи в списке Пачки: ● — есть несохранённые правки, ✓ — сохранён, ? — нет перевода."""
        if self.batch is None:
            return
        missing = set(self.batch_problems.no_translation + self.batch_problems.no_date) if self.batch_problems else set()
        for k, strip in enumerate(self.batch.strips):
            mark = " ●" if strip.unsaved else (" ✓" if strip.saved else "")
            if strip.name in missing:
                mark += "  ? нет перевода"
            item = self.list_strips.item(k)
            if item is not None and item.text() != strip.name + mark:
                item.setText(strip.name + mark)
        self.lbl_batch.setText(f"{self.batch_index + 1} из {len(self.batch.strips)}")

    def _report_batch_problems(self):
        problems = self.batch_problems
        if not problems:
            return
        parts = []
        if not self.current_txt_path:
            parts.append("Файл перевода ещё не загружен — кнопка «2. Перевод».")
        else:
            if problems.no_translation:
                parts.append("Нет Перевода для: " + ", ".join(problems.no_translation))
            if problems.no_strip:
                parts.append("Переводы без стрипа: " + ", ".join(problems.no_strip))
            if problems.duplicates:
                parts.append("Дата встречается дважды (взят первый Перевод): " + ", ".join(problems.duplicates))
        if problems.no_date:
            parts.append("В имени нет даты (сначала Датировка в Multi tool): " + ", ".join(problems.no_date))
        QMessageBox.information(self, "Пачка", "\n\n".join(parts))

    def save_all(self):
        if self.batch is None:
            return
        out = QFileDialog.getExistingDirectory(self, "Куда сохранить Пачку", result_path())
        if not out:
            return
        self.scene.clearSelection()

        def log(message):
            self.lbl_status.setText(message)
            QApplication.processEvents()

        errors = self.batch.save_all(out, log)
        self.refresh_strip_list()
        saved = len(self.batch.strips) - len(errors)
        text = f"Сохранено стрипов: {saved} из {len(self.batch.strips)} (PNG и проекты) в {out}"
        self.lbl_status.setText(text)
        if errors:
            QMessageBox.warning(self, "Пачка", text + "\n\nНе получилось:\n" + "\n".join(errors))
        else:
            QMessageBox.information(self, "Пачка", text)

    def _leave_batch(self) -> bool:
        """Закрыть Пачку (спросив про несохранённые стрипы). False — пользователь передумал."""
        if self.batch is None:
            return True
        if not self._confirm_unsaved():
            return False
        self.batch = None
        self.batch_index = -1
        self.batch_problems = None
        self.batch_panel.hide()
        self.act_save_all.setEnabled(False)
        return True

    def _confirm_unsaved(self) -> bool:
        unsaved = self.batch.unsaved() if self.batch is not None else []
        if not unsaved:
            return True
        names = ", ".join(s.name for s in unsaved[:5]) + (" …" if len(unsaved) > 5 else "")
        answer = QMessageBox.question(
            self, "Несохранённые стрипы",
            f"В Пачке есть несохранённые правки ({len(unsaved)}): {names}.\nЗакрыть без сохранения?")
        return answer == QMessageBox.StandardButton.Yes

    def closeEvent(self, event):
        if self._confirm_unsaved():
            event.accept()
        else:
            event.ignore()

    # ---------------------------------------------------------- экспорт PSD

    def export_psd(self):
        if self.document.image is None or self.psd_process is not None:
            return
        out, _ = QFileDialog.getSaveFileName(self, "Экспорт в PSD", result_path(self.strip_name + ".psd"),
                                             "Photoshop (*.psd)")
        if not out:
            return
        self.scene.clearSelection()
        try:
            job = psd.prepare(self.document, self.typography, out)
        except (ValueError, OSError) as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось подготовить PSD:\n{e}")
            return
        cmd = psd.photoshop_command(job)
        proc = QProcess(self)
        proc.finished.connect(lambda *_: self._psd_finished(job))
        proc.errorOccurred.connect(lambda *_: self._psd_finished(job))
        self.psd_process = proc
        self.act_export_psd.setEnabled(False)
        self.lbl_status.setText("Фотошоп собирает PSD… (первый запуск Фотошопа может занять минуту)")
        proc.start(cmd[0], cmd[1:])

    def _psd_finished(self, job):
        if self.psd_process is None:
            return
        self.psd_process.deleteLater()
        self.psd_process = None
        self.act_export_psd.setEnabled(True)
        ok, message = psd.result(job)
        if ok:
            self.lbl_status.setText(f"PSD сохранён: {job.psd_path.name}")
            text = f"PSD сохранён:\n{job.psd_path}"
            if message:
                text += f"\n\nПредупреждения Фотошопа:\n{message}"
            QMessageBox.information(self, "Готово", text)
        else:
            self.lbl_status.setText("PSD не собран")
            QMessageBox.warning(
                self, "PSD не собран",
                f"{message}\n\nМожно собрать вручную: в Фотошопе Файл → Сценарии → Обзор… "
                f"и выбрать файл\n{job.script}",
            )
