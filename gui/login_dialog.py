"""
Login / Register dialog.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from gui.styles import COLORS


class LoginDialog(QDialog):
    """Modal dialog for user login or registration."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("P2P Chat – Login")
        self.setFixedSize(420, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.username = ""
        self.password = ""
        self.bootstrap_host = "127.0.0.1"
        self.bootstrap_port = 9000
        self.peer_port = 5001
        self.is_register = False

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(32, 32, 32, 32)

        # Title
        title = QLabel("🔒 P2P Chat")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"font-size: 28px; font-weight: bold; color: {COLORS['accent']}; "
            "margin-bottom: 8px;"
        )
        layout.addWidget(title)

        subtitle = QLabel("Secure Peer-to-Peer Messaging")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(
            f"font-size: 13px; color: {COLORS['text_secondary']}; margin-bottom: 16px;"
        )
        layout.addWidget(subtitle)

        # Form
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._username_input = QLineEdit()
        self._username_input.setPlaceholderText("Enter username")
        form.addRow("Username:", self._username_input)

        self._password_input = QLineEdit()
        self._password_input.setPlaceholderText("Enter password")
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password:", self._password_input)

        self._bs_host_input = QLineEdit("127.0.0.1")
        self._bs_host_input.setPlaceholderText("Bootstrap host")
        form.addRow("Server IP:", self._bs_host_input)

        self._bs_port_input = QLineEdit("9000")
        self._bs_port_input.setPlaceholderText("Bootstrap port")
        form.addRow("Server Port:", self._bs_port_input)

        self._peer_port_input = QLineEdit("5001")
        self._peer_port_input.setPlaceholderText("Your peer port")
        form.addRow("Peer Port:", self._peer_port_input)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self._login_btn = QPushButton("Login")
        self._login_btn.clicked.connect(self._on_login)
        self._login_btn.setStyleSheet(
            f"background-color: {COLORS['accent']}; min-height: 38px;"
        )

        self._register_btn = QPushButton("Register")
        self._register_btn.clicked.connect(self._on_register)
        self._register_btn.setStyleSheet(
            f"background-color: {COLORS['accent_secondary']}; min-height: 38px;"
        )

        btn_layout.addWidget(self._login_btn)
        btn_layout.addWidget(self._register_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()

        # Footer
        footer = QLabel("End-to-End Encrypted • RSA + AES")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        layout.addWidget(footer)

    def _validate(self) -> bool:
        if not self._username_input.text().strip():
            QMessageBox.warning(self, "Error", "Username is required")
            return False
        if not self._password_input.text().strip():
            QMessageBox.warning(self, "Error", "Password is required")
            return False
        try:
            int(self._bs_port_input.text())
            int(self._peer_port_input.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "Ports must be numbers")
            return False
        return True

    def _collect_fields(self) -> None:
        self.username = self._username_input.text().strip()
        self.password = self._password_input.text().strip()
        self.bootstrap_host = self._bs_host_input.text().strip()
        self.bootstrap_port = int(self._bs_port_input.text().strip())
        self.peer_port = int(self._peer_port_input.text().strip())

    def _on_login(self) -> None:
        if self._validate():
            self._collect_fields()
            self.is_register = False
            self.accept()

    def _on_register(self) -> None:
        if self._validate():
            self._collect_fields()
            self.is_register = True
            self.accept()
