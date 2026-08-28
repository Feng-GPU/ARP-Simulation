from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QLabel


class HostDialog(QDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("编辑主机" if config else "添加主机")
        form = QFormLayout(self)
        self.name_edit = QLineEdit(config.name if config else "")
        self.ip_edit = QLineEdit(config.ip if config else "")
        self.mac_edit = QLineEdit(config.mac if config else "")
        form.addRow("名称", self.name_edit)
        form.addRow("IP 地址", self.ip_edit)
        form.addRow("MAC 地址", self.mac_edit)
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #c53030")
        form.addRow(self.error_label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self):
        return self.name_edit.text(), self.ip_edit.text(), self.mac_edit.text()
