"""Вкладка «Multi tool»: подготовка стрипов к публикации (rus_peanuts.publishing)."""
from qtpy.QtWidgets import (
    QButtonGroup, QCheckBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QRadioButton, QTextEdit, QVBoxLayout, QWidget,
)

from rus_peanuts import publishing


class MultiToolQtTab(QWidget):
    """Вкладка Multi tool for Pinats by Alimtair: подготовка стрипов к публикации (rus_peanuts.publishing)"""
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
        self.op_radios = {}
        for val, title in publishing.visible_operations().items():
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
        publishing.run(
            self.edit_path.text(),
            self.get_operation_value(),
            folder=self.rb_folder.isChecked(),
            contrast=self.chk_contrast.isChecked(),
            date=self.edit_date.text(),
            log=self.log,
        )
