from __future__ import annotations
from typing import Callable, Tuple, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QLabel, QCheckBox, QColorDialog, QMessageBox
)

class PaletteWidget(QWidget):
    """
    Simple palette list:
    - Each item stores rgb tuple in Qt.UserRole
    - Has enabled checkbox state in item checkstate
    """
    def __init__(
        self,
        on_changed: Callable[[], None],
        on_add_color_request: Callable[[], None],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._on_changed = on_changed
        self._on_add_color_request = on_add_color_request

        self.listw = QListWidget()
        self.listw.itemChanged.connect(lambda *_: self._on_changed())

        add_btn = QPushButton("Add (Picker)")
        add_btn.clicked.connect(self._on_add_color_request)

        add_dialog_btn = QPushButton("Add (Dialog)")
        add_dialog_btn.clicked.connect(self._add_color_dialog)

        rm_btn = QPushButton("Remove")
        rm_btn.clicked.connect(self._remove_selected)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear)

        top = QHBoxLayout()
        top.addWidget(add_btn)
        top.addWidget(add_dialog_btn)

        mid = QHBoxLayout()
        mid.addWidget(rm_btn)
        mid.addWidget(clear_btn)

        lay = QVBoxLayout()
        lay.addLayout(top)
        lay.addLayout(mid)
        lay.addWidget(QLabel("Palette (toggle to enable/disable):"))
        lay.addWidget(self.listw)
        self.setLayout(lay)

    def _add_color_dialog(self) -> None:
        col = QColorDialog.getColor(QColor(0, 255, 0), self, "Select Color to Remove")
        if not col.isValid():
            return
        self.add_color((col.red(), col.green(), col.blue()))
        self._on_changed()

    def _remove_selected(self) -> None:
        row = self.listw.currentRow()
        if row >= 0:
            self.listw.takeItem(row)
            self._on_changed()

    def _clear(self) -> None:
        self.listw.clear()
        self._on_changed()

    def add_color(self, rgb: Tuple[int, int, int]) -> None:
        item = QListWidgetItem(self._fmt(rgb))
        item.setData(Qt.UserRole, rgb)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        item.setCheckState(Qt.Checked)
        item.setToolTip("Enabled" if item.checkState() == Qt.Checked else "Disabled")
        self.listw.addItem(item)

    def colors(self) -> list[Tuple[Tuple[int, int, int], bool]]:
        out = []
        for i in range(self.listw.count()):
            it = self.listw.item(i)
            rgb = it.data(Qt.UserRole)
            enabled = (it.checkState() == Qt.Checked)
            out.append((rgb, enabled))
        return out

    @staticmethod
    def _fmt(rgb: Tuple[int, int, int]) -> str:
        r, g, b = rgb
        return f"RGB({r},{g},{b})  #{r:02X}{g:02X}{b:02X}"
