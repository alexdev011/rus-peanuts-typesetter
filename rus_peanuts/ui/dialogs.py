"""Окна «Руководство», «О нас» и «Изгиб текста»."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout

from . import embedded


def show_guide(parent):
    dlg = QDialog(parent)
    dlg.setWindowTitle("Как тут всё работает")
    dlg.setMinimumWidth(680)
    dlg.setStyleSheet("QDialog { background-color: white; } QLabel { color: #111; font-size: 13px; }")

    main_v = QVBoxLayout(dlg)
    content_h = QHBoxLayout()
    content_h.setSpacing(20)

    # Первая фотка СЛЕВА
    lbl_img = QLabel()
    lbl_img.setPixmap(embedded.pixmap(embedded.EMBEDDED_GUIDE_IMG_B64))
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


def show_about(parent):
    dlg = QDialog(parent)
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
    lbl_img.setPixmap(embedded.pixmap(embedded.EMBEDDED_ABOUT_IMG_B64))
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


def arch_dialog(parent, items) -> None:
    """Ползунок Изгиба для выделенных блоков; меняет их сразу, пока двигается."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Изгиб текста")
    dlg.setMinimumWidth(360)
    v = QVBoxLayout(dlg)

    init_val = items[0].block.arch
    lbl = QLabel(f"Сила изгиба: {init_val} (плюс — дуга вверх, минус — дуга вниз)")
    v.addWidget(lbl)

    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setMinimum(-120)
    slider.setMaximum(120)
    slider.setValue(init_val)
    v.addWidget(slider)

    def on_val_change(val):
        lbl.setText(f"Сила изгиба: {val} (плюс — дуга вверх, минус — дуга вниз)")
        for item in items:
            item.block.set_arch(val)
            item.refresh()

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
