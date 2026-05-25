"""
Peer list widget – sidebar showing online/offline peers and groups.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.styles import ADD_GROUP_BUTTON_STYLE, COLORS, SIDEBAR_STYLE


class PeerListWidget(QWidget):
    """Sidebar with peer list and group list."""

    peer_selected = pyqtSignal(str)       # username
    group_selected = pyqtSignal(str)      # group_id
    create_group_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setMaximumWidth(280)
        self.setStyleSheet(SIDEBAR_STYLE)

        self._peers: dict[str, dict] = {}   # {username: {status, ...}}
        self._groups: dict[str, dict] = {}  # {group_id: {group_name, ...}}

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Peers section ──────────────────────────────────
        peers_header = QLabel("  PEERS")
        peers_header.setStyleSheet(
            f"font-size: 11px; font-weight: bold; color: {COLORS['text_muted']}; "
            f"padding: 12px 8px 6px 8px; background-color: {COLORS['bg_secondary']};"
        )
        layout.addWidget(peers_header)

        self._peer_list = QListWidget()
        self._peer_list.itemClicked.connect(self._on_peer_clicked)
        layout.addWidget(self._peer_list, stretch=3)

        # ── Groups section ─────────────────────────────────
        groups_header_widget = QWidget()
        groups_header_widget.setStyleSheet(
            f"background-color: {COLORS['bg_secondary']}; "
            f"border-top: 1px solid {COLORS['border']}; "
            f"border-bottom: 1px solid transparent;"
        )
        groups_header_layout = QHBoxLayout(groups_header_widget)
        groups_header_layout.setContentsMargins(8, 8, 8, 4)

        groups_label = QLabel("  GROUPS")
        groups_label.setStyleSheet(
            f"font-size: 11px; font-weight: bold; color: {COLORS['text_muted']}; border: none;"
        )
        groups_header_layout.addWidget(groups_label)
        groups_header_layout.addStretch()

        add_group_btn = QPushButton("+ New")
        add_group_btn.setStyleSheet(ADD_GROUP_BUTTON_STYLE)
        add_group_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_group_btn.clicked.connect(self.create_group_clicked.emit)
        groups_header_layout.addWidget(add_group_btn)

        layout.addWidget(groups_header_widget)

        self._group_list = QListWidget()
        self._group_list.itemClicked.connect(self._on_group_clicked)
        layout.addWidget(self._group_list, stretch=2)

    # ── public API ─────────────────────────────────────────

    def set_peers(self, peers: dict[str, dict]) -> None:
        """Replace the entire peer list.  {username: {status, ...}}"""
        self._peers = peers
        self._refresh_peer_list()

    def update_peer(self, username: str, status: str) -> None:
        if username not in self._peers:
            self._peers[username] = {}
        self._peers[username]["status"] = status
        self._refresh_peer_list()

    def increment_direct_unread(self, username: str) -> None:
        if username not in self._peers:
            self._peers[username] = {}
        count = self._peers[username].get("unread", 0)
        self._peers[username]["unread"] = count + 1
        self._refresh_peer_list()

    def clear_direct_unread(self, username: str) -> None:
        if username in self._peers and "unread" in self._peers[username]:
            self._peers[username]["unread"] = 0
            self._refresh_peer_list()

    def remove_peer(self, username: str) -> None:
        self._peers.pop(username, None)
        self._refresh_peer_list()

    def set_groups(self, groups: list[dict]) -> None:
        self._groups = {g["group_id"]: g for g in groups}
        self._refresh_group_list()

    def add_group(self, group_info: dict) -> None:
        self._groups[group_info["group_id"]] = group_info
        self._refresh_group_list()

    # ── internal ───────────────────────────────────────────

    def _refresh_peer_list(self) -> None:
        self._peer_list.clear()
        # Sort: online first
        sorted_peers = sorted(
            self._peers.items(),
            key=lambda x: (0 if x[1].get("status") == "online" else 1, x[0]),
        )
        for username, info in sorted_peers:
            status = info.get("status", "online")
            unread = info.get("unread", 0)
            icon = "🟢" if status == "online" else "🔴"
            
            text = f"  {icon}  {username}"
            if unread > 0:
                text += f" ({unread})"
                
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, username)
            self._peer_list.addItem(item)

    def _refresh_group_list(self) -> None:
        self._group_list.clear()
        for gid, info in self._groups.items():
            name = info.get("group_name", gid[:8])
            members_count = len(info.get("members", []))
            unread = info.get("unread", 0)
            
            text = f"  📁  {name}  ({members_count})"
            if unread > 0:
                text += f" ({unread})"
                
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, gid)
            self._group_list.addItem(item)

    def increment_group_unread(self, group_id: str) -> None:
        if group_id in self._groups:
            count = self._groups[group_id].get("unread", 0)
            self._groups[group_id]["unread"] = count + 1
            self._refresh_group_list()

    def clear_group_unread(self, group_id: str) -> None:
        if group_id in self._groups and "unread" in self._groups[group_id]:
            self._groups[group_id]["unread"] = 0
            self._refresh_group_list()

    def _on_peer_clicked(self, item: QListWidgetItem) -> None:
        username = item.data(Qt.ItemDataRole.UserRole)
        if username:
            self.peer_selected.emit(username)

    def _on_group_clicked(self, item: QListWidgetItem) -> None:
        group_id = item.data(Qt.ItemDataRole.UserRole)
        if group_id:
            self.group_selected.emit(group_id)
