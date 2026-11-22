"""Главное окно: вкладка вёрстки (холст + панель кнопок) и вкладка Multi tool."""
import os

from PyQt6.QtCore import QProcess, QRectF, Qt
from PyQt6.QtGui import QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFileDialog, QGraphicsScene, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from rus_peanuts.export import psd
from rus_peanuts.export.png import export_png
from rus_peanuts.typesetting import analysis, project, translation
from rus_peanuts.typesetting.document import Document
from rus_peanuts.typesetting.layout import Typography

from . import dialogs, embedded
from rus_peanuts.typesetting.graphics import to_qpixmap

from .block_item import BlockItem
from .canvas import StripCanvasView
from .multitool_tab import MultiToolQtTab


cv2_to_qpixmap = to_qpixmap


class MainWindow(QMainWindow):
    def __init__(self, typography: Typography):
        super().__init__()
        self.setWindowTitle("RUS PEANUTS — Auto-Typesetter")
        self.resize(1320, 860)
        self.setAcceptDrops(True)

        self.typography = typography
        self.document = Document(typography)
        self.current_txt_path = None
        self.strip_name = "strip"
        self.psd_process = None
        self.cleaned_pixmap = None
        self.orig_qpixmap = None
        self.pixmap_item = None
        self.items: list[BlockItem] = []

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
        self.tabs.addTab(self.tab_multitool, "2. Multi tool for Pinats by Alimtair")

        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self.undo_action)
        self.init_file_menu()

    def init_file_menu(self):
        """Меню «Файл»: проект и экспорт (панель кнопок и так во всю ширину экрана)."""
        menu = self.menuBar().addMenu("Файл")
        menu.addAction("Загрузить стрип…", self.open_image_dialog)
        menu.addAction("Загрузить перевод (.txt)…", self.open_txt_dialog)
        menu.addSeparator()
        self.act_open_project = menu.addAction("Открыть проект…", QKeySequence("Ctrl+O"), self.open_project_dialog)
        self.act_save_project = menu.addAction("Сохранить проект…", QKeySequence("Ctrl+S"), self.save_project)
        menu.addSeparator()
        menu.addAction("Сохранить PNG…", self.save_result)
        self.act_export_psd = menu.addAction("Экспорт в PSD (через Фотошоп)…", self.export_psd)
        self.act_export_psd.setStatusTip("PSD с настоящими текстовыми слоями — его соберёт Фотошоп")

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

    def selected_items(self) -> list[BlockItem]:
        return [it for it in self.scene.selectedItems() if isinstance(it, BlockItem)]

    def checkpoint(self):
        selected = [i for i, it in enumerate(self.items) if it.isSelected()]
        self.document.checkpoint(selected)
        self.update_undo_button()

    def drop_checkpoint(self):
        self.document.drop_checkpoint()
        self.update_undo_button()

    def update_undo_button(self):
        self.btn_undo.setEnabled(self.document.can_undo)

    def undo_action(self):
        selected = self.document.undo()
        if selected is None:
            return
        self.rebuild_scene(selected)
        self.lbl_status.setText("Действие отменено!")

    # ---------------------------------------------------- загрузка файлов

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
            elif ext == project.EXTENSION:
                self.load_project(path)

    def open_image_dialog(self):
        f, _ = QFileDialog.getOpenFileName(self, "Выбрать стрип", "", "Изображения (*.png *.jpg *.jpeg)")
        if f:
            self.load_image(f)

    def open_txt_dialog(self):
        f, _ = QFileDialog.getOpenFileName(self, "Выбрать перевод", "", "Текст (*.txt)")
        if f:
            self.load_txt(f)

    def load_image(self, path):
        img = analysis.load_image(path)
        if img is None:
            QMessageBox.critical(self, "Ошибка", "Не удалось открыть изображение.")
            return
        # Перевод перечитывается с диска: если файл поправили, подхватятся изменения
        lines = translation.read(self.current_txt_path) if self.current_txt_path else None
        self.document.open_strip(img, lines)
        self.strip_name = os.path.splitext(os.path.basename(path))[0]
        self.orig_qpixmap = None
        self.rebuild_scene()
        self._show_counts()

    def load_txt(self, path):
        self.current_txt_path = path
        lines = translation.read(path)
        if lines is None:
            return
        self.document.set_translation(lines)
        self.rebuild_scene()
        self._show_counts()

    def _show_counts(self):
        doc = self.document
        if doc.lines is None:
            self.lbl_status.setText(
                f"Стрип очищен! Найдено баблов: {len(doc.bubbles)}, звуков/SFX: {len(doc.sounds)}."
            )
        else:
            self.lbl_status.setText(
                f"Найдено баблов: {len(doc.bubbles)}, SFX: {len(doc.sounds)} | Расставлено фраз: {len(doc.lines)}."
            )

    # ------------------------------------------------------- правка блоков

    def _edit_selected(self, change):
        items = self.selected_items()
        if items:
            self.checkpoint()
            for item in items:
                change(item.block)
                item.refresh()

    def adjust_font(self, delta):
        self._edit_selected(lambda b: b.grow(delta))

    def adjust_width(self, delta):
        self._edit_selected(lambda b: b.widen(delta))

    def toggle_italic(self):
        self._edit_selected(lambda b: b.toggle_italic())

    def adjust_stretch(self, delta):
        self._edit_selected(lambda b: b.stretch_by(delta))

    def adjust_weight(self, delta):
        self._edit_selected(lambda b: b.thicken(delta))

    def toggle_selected_outline(self):
        self._edit_selected(lambda b: b.toggle_shadow())

    def open_arch_dialog(self):
        items = self.selected_items()
        if not items:
            QMessageBox.information(self, "Изгиб текста", "Сначала кликни на нужный текст на стрипе, чтобы выделить его.")
            return
        self.checkpoint()
        dialogs.arch_dialog(self, items)

    def keyPressEvent(self, event):
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

    # ---------------------------------------------------------------- Ластик

    @property
    def can_erase(self) -> bool:
        return self.cleaned_pixmap is not None

    def erase_at(self, x, y):
        if self.pixmap_item is not None and self.document.erase_spot(x, y):
            self.cleaned_pixmap = cv2_to_qpixmap(self.document.image)
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
        out, _ = QFileDialog.getSaveFileName(self, "Сохранить", "strip_done.png", "PNG (*.png)")
        if out:
            export_png(self.document, self.typography, out)
            QMessageBox.information(self, "Готово", "Стрип сохранен!")

    # ------------------------------------------------------------- проект

    def open_project_dialog(self):
        f, _ = QFileDialog.getOpenFileName(self, "Открыть проект", "", f"Проект RUS PEANUTS (*{project.EXTENSION})")
        if f:
            self.load_project(f)

    def load_project(self, path):
        try:
            doc = project.load(path, self.typography)
        except (project.ProjectError, OSError) as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть проект:\n{e}")
            return
        self.document = doc
        self.current_txt_path = None  # Перевод уже внутри проекта
        self.strip_name = os.path.splitext(os.path.basename(path))[0]
        self.orig_qpixmap = None
        self.rebuild_scene()
        self.lbl_status.setText(f"Проект открыт: {os.path.basename(path)} | Текстовых блоков: {len(doc.blocks)}.")

    def save_project(self):
        if self.document.analysis is None:
            return
        out, _ = QFileDialog.getSaveFileName(self, "Сохранить проект", self.strip_name + project.EXTENSION,
                                             f"Проект RUS PEANUTS (*{project.EXTENSION})")
        if not out:
            return
        try:
            project.save(self.document, out)
        except (project.ProjectError, OSError) as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить проект:\n{e}")
            return
        self.lbl_status.setText(f"Проект сохранён: {os.path.basename(out)}")

    # ---------------------------------------------------------- экспорт PSD

    def export_psd(self):
        if self.document.image is None or self.psd_process is not None:
            return
        out, _ = QFileDialog.getSaveFileName(self, "Экспорт в PSD", self.strip_name + ".psd", "Photoshop (*.psd)")
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
