"""
Chat widget – displays message bubbles.
"""

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from gui.styles import COLORS


class ChatBubble(QWidget):
    """A single message bubble."""

    def __init__(self, sender: str, content: str, timestamp: str, is_own: bool, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        # Determine alignment
        alignment = Qt.AlignmentFlag.AlignRight if is_own else Qt.AlignmentFlag.AlignLeft

        # Sender label
        if not is_own:
            sender_label = QLabel(sender)
            sender_label.setStyleSheet(
                f"color: {COLORS['accent']}; font-size: 11px; font-weight: bold; "
                "background: transparent;"
            )
            sender_label.setAlignment(alignment)
            layout.addWidget(sender_label)

        # Message content
        msg_label = QLabel(content)
        msg_label.setWordWrap(True)
        msg_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bg_color = COLORS["message_sent"] if is_own else COLORS["message_received"]
        border_radius = "18px 18px 4px 18px" if is_own else "18px 18px 18px 4px"
        border = "none" if is_own else f"1px solid {COLORS['border']}"
        msg_label.setStyleSheet(
            f"background-color: {bg_color}; "
            f"border-radius: {border_radius}; "
            f"border: {border}; "
            f"padding: 10px 16px; "
            f"color: {COLORS['text_primary']}; "
            f"font-size: 14px;"
        )
        msg_label.setMaximumWidth(400)
        layout.addWidget(msg_label, alignment=alignment)

        # Timestamp
        ts_display = timestamp
        if isinstance(timestamp, str) and timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                ts_display = dt.strftime("%H:%M")
            except Exception:
                ts_display = timestamp[:5] if len(timestamp) >= 5 else timestamp

        time_label = QLabel(ts_display)
        time_label.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: 10px; background: transparent;"
        )
        time_label.setAlignment(alignment)
        layout.addWidget(time_label)


class ChatWidget(QScrollArea):
    """Scrollable area containing chat bubbles."""

    def __init__(self, own_username: str, parent=None):
        super().__init__(parent)
        self.own_username = own_username
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("border: none; background: transparent;")
        self.history_loaded = False
        self.displayed_messages = set()

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.setSpacing(4)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.addStretch()

        self.setWidget(self._container)

    def add_message(self, sender: str, content: str, timestamp: str = "", message_id: str = "") -> None:
        """Add a message bubble to the chat."""
        if message_id and message_id in self.displayed_messages:
            return
        if message_id:
            self.displayed_messages.add(message_id)

        is_own = sender == self.own_username
        bubble = ChatBubble(sender, content, timestamp, is_own)

        # Insert before the stretch
        self._layout.insertWidget(self._layout.count() - 1, bubble)

        # Auto-scroll to bottom
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def clear_messages(self) -> None:
        """Remove all bubbles."""
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self.displayed_messages.clear()

    def load_history(self, messages: list[dict]) -> None:
        """Load messages from history: [{sender, content, timestamp, message_id}]."""
        self.clear_messages()
        for m in messages:
            self.add_message(m["sender"], m["content"], str(m.get("timestamp", "")), m.get("message_id", ""))
        self.history_loaded = True

    def scroll_to_bottom(self) -> None:
        """Force scroll to the latest message."""
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(100, lambda: self.verticalScrollBar().setValue(
            self.verticalScrollBar().maximum()
        ))
