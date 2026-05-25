"""
Group creation dialog.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.styles import COLORS


class GroupDialog(QDialog):
    """Dialog for creating a new group chat."""

    def __init__(self, available_peers: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create Group")
        self.setFixedSize(360, 440)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.group_name = ""
        self.selected_members: list[str] = []

        self._peer_checkboxes: list[tuple[str, QCheckBox]] = []
        self._build_ui(available_peers)

    def _build_ui(self, peers: list[str]) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title = QLabel("📁 Create Group Chat")
        title.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {COLORS['accent']};"
        )
        layout.addWidget(title)

        # Group name
        layout.addWidget(QLabel("Group Name:"))
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Enter group name")
        layout.addWidget(self._name_input)

        # Members
        layout.addWidget(QLabel("Select Members:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        members_widget = QWidget()
        members_layout = QVBoxLayout(members_widget)
        members_layout.setSpacing(6)

        for peer in sorted(peers):
            cb = QCheckBox(peer)
            cb.setStyleSheet(
                f"QCheckBox {{ color: {COLORS['text_primary']}; font-size: 14px; padding: 4px; }}"
                f"QCheckBox::indicator {{ width: 18px; height: 18px; }}"
            )
            self._peer_checkboxes.append((peer, cb))
            members_layout.addWidget(cb)

        members_layout.addStretch()
        scroll.setWidget(members_widget)
        layout.addWidget(scroll, stretch=1)

        # Create button
        create_btn = QPushButton("Create Group")
        create_btn.setStyleSheet(f"min-height: 38px;")
        create_btn.clicked.connect(self._on_create)
        layout.addWidget(create_btn)

    def _on_create(self) -> None:
        name = self._name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Group name is required")
            return

        selected = [peer for peer, cb in self._peer_checkboxes if cb.isChecked()]
        if not selected:
            QMessageBox.warning(self, "Error", "Select at least one member")
            return

        self.group_name = name
        self.selected_members = selected
        self.accept()
