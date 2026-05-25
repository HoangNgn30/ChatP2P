"""
Main application window – ties together all GUI components and the PeerNode.
"""

import asyncio
from datetime import datetime
from utils.timezone import TZ_UTC7
from functools import partial

from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from gui.chat_widget import ChatWidget
from gui.group_dialog import GroupDialog
from gui.manage_group_dialog import ManageGroupDialog
from gui.peer_list_widget import PeerListWidget
from gui.styles import (
    CHAT_AREA_STYLE,
    COLORS,
    ENCRYPTION_BADGE_STYLE,
    HEADER_STYLE,
    MAIN_STYLE,
    MESSAGE_INPUT_STYLE,
    SEND_BUTTON_STYLE,
)
from utils.logger import get_logger

log = get_logger(__name__)


class SignalBridge(QObject):
    """
    Bridge between asyncio callbacks and Qt signals.
    We need this because Qt GUI updates must happen on the main thread.
    """
    message_received = pyqtSignal(str, str, str, str, str, str)  # sender, content, ts, type, group_id, message_id
    peer_update = pyqtSignal(str, dict)                      # action, peer_info
    group_invite = pyqtSignal(str, str, str, list)            # gid, name, by, members
    groups_list = pyqtSignal(list)                            # groups
    group_member_added = pyqtSignal(str, str, str, str, list) # gid, name, new_member, by, members
    group_member_removed = pyqtSignal(str, str, str, str, list) # gid, name, removed, by, members
    typing_signal = pyqtSignal(str)                           # sender


class MainWindow(QMainWindow):
    """The main chat window."""

    def __init__(self, peer_node, loop: asyncio.AbstractEventLoop, parent=None):
        super().__init__(parent)
        self.peer_node = peer_node
        self.loop = loop

        # Current chat target
        self._current_chat: str | None = None   # username or None
        self._current_group: str | None = None  # group_id or None
        self._chat_widgets: dict[str, ChatWidget] = {}

        self.setWindowTitle(
            f"P2P Chat – {peer_node.username}@{peer_node.host}:{peer_node.port}"
        )
        self.setMinimumSize(900, 600)
        self.resize(1000, 650)
        self.setStyleSheet(MAIN_STYLE)

        # Signal bridge
        self._signals = SignalBridge()
        self._signals.message_received.connect(self._on_message_received)
        self._signals.peer_update.connect(self._on_peer_update)
        self._signals.group_invite.connect(self._on_group_invite)
        self._signals.groups_list.connect(self._on_groups_list)
        self._signals.group_member_added.connect(self._on_group_member_added)
        self._signals.group_member_removed.connect(self._on_group_member_removed)
        self._signals.typing_signal.connect(self._on_typing)

        self._build_ui()
        self._connect_peer_callbacks()

    # ── UI construction ────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── Sidebar ──────────────────────────────────────
        self._sidebar = PeerListWidget()
        self._sidebar.peer_selected.connect(self._open_peer_chat)
        self._sidebar.group_selected.connect(self._open_group_chat)
        self._sidebar.create_group_clicked.connect(self._show_create_group)
        splitter.addWidget(self._sidebar)

        # ── Chat area ────────────────────────────────────
        chat_area = QWidget()
        chat_area.setStyleSheet(CHAT_AREA_STYLE)
        chat_layout = QVBoxLayout(chat_area)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        # Header
        self._header_widget = QWidget()
        self._header_widget.setStyleSheet(HEADER_STYLE)
        header_layout = QHBoxLayout(self._header_widget)
        header_layout.setContentsMargins(16, 8, 16, 8)

        self._chat_title = QLabel("💬 Select a peer or group to start chatting")
        self._chat_title.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {COLORS['text_primary']};"
        )
        header_layout.addWidget(self._chat_title)
        
        self._manage_members_btn = QPushButton("Manage Members")
        self._manage_members_btn.setStyleSheet(f"color: {COLORS['accent']}; padding: 4px;")
        self._manage_members_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._manage_members_btn.clicked.connect(self._show_manage_group)
        self._manage_members_btn.hide()
        header_layout.addWidget(self._manage_members_btn)
        
        header_layout.addStretch()

        self._typing_label = QLabel("")
        self._typing_label.setStyleSheet(
            f"font-size: 12px; color: {COLORS['text_muted']}; font-style: italic;"
        )
        header_layout.addWidget(self._typing_label)

        chat_layout.addWidget(self._header_widget)

        # Chat display (placeholder)
        self._chat_container = QWidget()
        self._chat_container_layout = QVBoxLayout(self._chat_container)
        self._chat_container_layout.setContentsMargins(0, 0, 0, 0)

        self._empty_chat = ChatWidget(self.peer_node.username)
        self._chat_container_layout.addWidget(self._empty_chat)
        self._active_chat_widget = self._empty_chat

        chat_layout.addWidget(self._chat_container, stretch=1)

        # Input area
        input_widget = QWidget()
        input_widget.setStyleSheet(
            f"background-color: {COLORS['bg_secondary']}; "
            f"border-top: 1px solid {COLORS['border']};"
        )
        input_layout = QHBoxLayout(input_widget)
        input_layout.setContentsMargins(12, 10, 12, 10)
        input_layout.setSpacing(10)

        encrypt_badge = QLabel("🔒")
        encrypt_badge.setStyleSheet(ENCRYPTION_BADGE_STYLE)
        encrypt_badge.setToolTip("End-to-End Encrypted")
        input_layout.addWidget(encrypt_badge)

        self._msg_input = QLineEdit()
        self._msg_input.setPlaceholderText("Type a message…")
        self._msg_input.setStyleSheet(MESSAGE_INPUT_STYLE)
        self._msg_input.returnPressed.connect(self._send_message)
        input_layout.addWidget(self._msg_input, stretch=1)

        send_btn = QPushButton("Send")
        send_btn.setStyleSheet(SEND_BUTTON_STYLE)
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(send_btn)

        chat_layout.addWidget(input_widget)

        splitter.addWidget(chat_area)
        splitter.setStretchFactor(0, 0)  # sidebar fixed
        splitter.setStretchFactor(1, 1)  # chat stretches

        main_layout.addWidget(splitter)

        # ── Status bar ───────────────────────────────────
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        peer_count = len(self.peer_node.known_peers)
        status_bar.showMessage(
            f"  Connected to Bootstrap  |  Peers: {peer_count} online  |  🔒 E2E Encrypted"
        )
        self._status_bar = status_bar

        # Populate sidebar
        self._populate_sidebar()

    def _populate_sidebar(self) -> None:
        """Fill sidebar with known peers from initial connection."""
        peers = {}
        for username, info in self.peer_node.known_peers.items():
            peers[username] = {"status": "online"}
        self._sidebar.set_peers(peers)

        groups = list(self.peer_node.groups.values())
        if groups:
            self._sidebar.set_groups(groups)

    # ── peer node callbacks ────────────────────────────────

    def _connect_peer_callbacks(self) -> None:
        """Wire PeerNode callbacks to Qt signals via the bridge."""
        handler = self.peer_node.message_handler

        def on_msg(sender, content, ts, msg_type, group_id, message_id):
            self._signals.message_received.emit(
                sender, content, ts, msg_type, group_id or "", message_id or ""
            )

        def on_peer_upd(action, peer_info):
            self._signals.peer_update.emit(action, peer_info)

        def on_group_inv(gid, name, by, members):
            self._signals.group_invite.emit(gid, name, by, members)

        def on_groups(groups):
            self._signals.groups_list.emit(groups)

        def on_group_member_added(gid, name, new_member, by, members):
            self._signals.group_member_added.emit(gid, name, new_member, by, members)
            
        def on_group_member_removed(gid, name, removed, by, members):
            self._signals.group_member_removed.emit(gid, name, removed, by, members)

        def on_typing(sender):
            self._signals.typing_signal.emit(sender)

        handler.on_message_received = on_msg
        handler.on_peer_update = on_peer_upd
        handler.on_group_invite = on_group_inv
        handler.on_groups_list = on_groups
        handler.on_group_member_added = on_group_member_added
        handler.on_group_member_removed = on_group_member_removed
        handler.on_typing = on_typing

    # ── signal handlers ────────────────────────────────────

    def _on_message_received(
        self, sender: str, content: str, ts: str, msg_type: str, group_id: str | None, message_id: str
    ) -> None:
        log.info(f"UI _on_message_received called: sender={sender}, type={msg_type}, group_id={group_id}, content={content[:20]}")
        if msg_type == "direct":
            key = sender
            chat = self._get_or_create_chat(sender)
            chat.add_message(sender, content, ts, message_id)
            
            # Only show notification if NOT currently viewing this chat
            if self._current_chat != sender:
                self._sidebar.increment_direct_unread(sender)
                
        elif msg_type == "group":
            chat = self._get_or_create_group_chat(group_id)
            chat.add_message(sender, content, ts, message_id)
            if self._current_group != group_id:
                self._sidebar.increment_group_unread(group_id)
                group_info = self.peer_node.groups.get(group_id, {})
                name = group_info.get("group_name", group_id[:8])
                self._status_bar.showMessage(f"  💬 New message in {name}")

    def _on_peer_update(self, action: str, peer_info: dict) -> None:
        username = peer_info.get("username", "")
        if action == "joined":
            self._sidebar.update_peer(username, "online")
            self._status_bar.showMessage(f"  🟢 {username} joined the network")
        elif action == "left":
            self._sidebar.update_peer(username, "offline")
            self._status_bar.showMessage(f"  🔴 {username} left the network")

        # Update peer count
        online = sum(
            1 for p in self.peer_node.known_peers.values()
        )
        self._status_bar.showMessage(
            f"  Peers: {online} online  |  🔒 E2E Encrypted"
        )

    def _on_group_invite(
        self, group_id: str, group_name: str, invited_by: str, members: list
    ) -> None:
        self._sidebar.add_group(
            {"group_id": group_id, "group_name": group_name, "members": members}
        )
        self._status_bar.showMessage(
            f"  📁 {invited_by} added you to group '{group_name}'"
        )

    def _on_groups_list(self, groups: list) -> None:
        self._sidebar.set_groups(groups)

    def _on_group_member_added(self, group_id: str, group_name: str, new_member: str, added_by: str, members: list) -> None:
        # Update sidebar
        self._sidebar.add_group(
            {"group_id": group_id, "group_name": group_name, "members": members}
        )
        self._status_bar.showMessage(
            f"  📁 {added_by} added {new_member} to group '{group_name}'"
        )
        # Update title if it's the current chat
        if self._current_group == group_id:
            self._chat_title.setText(f"📁 {group_name}  ({len(members)} members)")

    def _on_group_member_removed(self, group_id: str, group_name: str, removed_member: str, removed_by: str, members: list) -> None:
        if removed_member == self.peer_node.username:
            # We were removed
            self._status_bar.showMessage(f"  📁 {removed_by} removed you from group '{group_name}'")
            # Close the chat if it is the current one
            if self._current_group == group_id:
                self._current_group = None
                self._chat_title.setText("💬 Select a peer or group to start chatting")
                self._manage_members_btn.hide()
                self._switch_chat_widget(self._empty_chat)
            # Fetch groups again to sync sidebar
            asyncio.run_coroutine_threadsafe(self.peer_node.refresh_peers(), self.loop)
            # A bit of a hack: to remove from sidebar properly without writing remove logic
            # Just rebuild groups (or we can just reload groups from peer_node)
            self._sidebar.set_groups(list(self.peer_node.groups.values()))
        else:
            self._status_bar.showMessage(f"  📁 {removed_by} removed {removed_member} from group '{group_name}'")
            self._sidebar.add_group(
                {"group_id": group_id, "group_name": group_name, "members": members}
            )
            if self._current_group == group_id:
                self._chat_title.setText(f"📁 {group_name}  ({len(members)} members)")

    def _on_typing(self, sender: str) -> None:
        if sender == self._current_chat:
            self._typing_label.setText(f"{sender} is typing…")
            QTimer.singleShot(3000, lambda: self._typing_label.setText(""))

    # ── chat management ────────────────────────────────────

    def _open_peer_chat(self, username: str) -> None:
        """Switch to 1-1 chat with *username*."""
        self._current_chat = username
        self._current_group = None
        self._chat_title.setText(f"💬 Chat with: {username}")
        self._manage_members_btn.hide()
        
        self._sidebar.clear_direct_unread(username)

        chat = self._get_or_create_chat(username)
        self._switch_chat_widget(chat)

        if not chat.history_loaded:
            # Load history without blocking the event loop
            task = self.loop.create_task(self.peer_node.get_chat_history(username))
            
            def on_chat_history_loaded(t):
                try:
                    history = t.result()
                    if history:
                        chat.load_history(history)
                    chat.scroll_to_bottom()
                except Exception as e:
                    print(f"Error loading chat history: {e}")
            
            task.add_done_callback(on_chat_history_loaded)
        else:
            chat.scroll_to_bottom()

    def _open_group_chat(self, group_id: str) -> None:
        """Switch to group chat."""
        self._current_chat = None
        self._current_group = group_id
        
        self._sidebar.clear_group_unread(group_id)

        group_info = self.peer_node.groups.get(group_id, {})
        name = group_info.get("group_name", group_id[:8])
        members = group_info.get("members", [])
        self._chat_title.setText(f"📁 {name}  ({len(members)} members)")
        self._manage_members_btn.show()

        chat = self._get_or_create_group_chat(group_id)
        self._switch_chat_widget(chat)

        if not chat.history_loaded:
            # Load history without blocking the event loop
            task = self.loop.create_task(self.peer_node.get_group_history(group_id))
            
            def on_group_history_loaded(t):
                try:
                    history = t.result()
                    if history:
                        chat.load_history(history)
                    chat.scroll_to_bottom()
                except Exception as e:
                    print(f"Error loading group history: {e}")
                    
            task.add_done_callback(on_group_history_loaded)
        else:
            chat.scroll_to_bottom()

    def _get_or_create_chat(self, username: str) -> ChatWidget:
        key = f"dm_{username}"
        if key not in self._chat_widgets:
            self._chat_widgets[key] = ChatWidget(self.peer_node.username)
        return self._chat_widgets[key]

    def _get_or_create_group_chat(self, group_id: str) -> ChatWidget:
        key = f"group_{group_id}"
        if key not in self._chat_widgets:
            self._chat_widgets[key] = ChatWidget(self.peer_node.username)
        return self._chat_widgets[key]

    def _switch_chat_widget(self, chat: ChatWidget) -> None:
        """Swap the visible chat widget."""
        # Hide current
        if self._active_chat_widget:
            self._chat_container_layout.removeWidget(self._active_chat_widget)
            self._active_chat_widget.setParent(None)

        self._chat_container_layout.addWidget(chat)
        self._active_chat_widget = chat

    # ── send message ───────────────────────────────────────

    def _send_message(self) -> None:
        text = self._msg_input.text().strip()
        if not text:
            return

        if self._current_chat:
            # Direct message
            # UI relies on DB load for consistency, but we append directly here.
            chat = self._get_or_create_chat(self._current_chat)
            chat.add_message(
                self.peer_node.username,
                text,
                datetime.now(TZ_UTC7).isoformat(),
                # Temporarily pass empty message_id since we don't know it yet
                ""
            )
            self._msg_input.clear()

            asyncio.run_coroutine_threadsafe(
                self.peer_node.send_message(self._current_chat, text),
                self.loop,
            )

        elif self._current_group:
            # Group message
            chat = self._get_or_create_group_chat(self._current_group)
            chat.add_message(
                self.peer_node.username,
                text,
                datetime.now(TZ_UTC7).isoformat(),
                ""
            )
            self._msg_input.clear()

            asyncio.run_coroutine_threadsafe(
                self.peer_node.send_group_message(self._current_group, text),
                self.loop,
            )
        else:
            self._status_bar.showMessage("  Select a peer or group first")

    # ── create group ───────────────────────────────────────

    def _show_create_group(self) -> None:
        peers = list(self.peer_node.known_peers.keys())
        if not peers:
            QMessageBox.information(self, "Info", "No peers online to create a group with")
            return

        dialog = GroupDialog(peers, self)
        if dialog.exec():
            asyncio.run_coroutine_threadsafe(
                self._do_create_group(dialog.group_name, dialog.selected_members),
                self.loop,
            )

    async def _do_create_group(self, name: str, members: list[str]) -> None:
        result = await self.peer_node.create_group(name, members)
        if result:
            self._signals.group_invite.emit(
                result["group_id"],
                result["group_name"],
                self.peer_node.username,
                result["members"],
            )

    def _show_manage_group(self) -> None:
        if not self._current_group:
            return
            
        group_info = self.peer_node.groups.get(self._current_group)
        if not group_info:
            return
            
        group_id = group_info["group_id"]
        group_name = group_info["group_name"]
        members = group_info.get("members", [])
        
        all_peers = list(self.peer_node.known_peers.keys())
        # The user themself can also be part of the group, and they are usually not in known_peers
        if self.peer_node.username not in all_peers:
            all_peers.append(self.peer_node.username)
            
        dialog = ManageGroupDialog(group_id, group_name, members, all_peers, self.peer_node.username, self)
        dialog.exec()

    # ── cleanup ────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Graceful disconnect on window close."""
        asyncio.run_coroutine_threadsafe(
            self.peer_node.disconnect(), self.loop
        )
        event.accept()
