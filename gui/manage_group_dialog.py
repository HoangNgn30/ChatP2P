"""
Dialog to manage group members (add/remove).
"""

import asyncio
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.styles import COLORS


class ManageGroupDialog(QDialog):
    """Dialog for adding and removing members from a group."""

    def __init__(self, group_id: str, group_name: str, current_members: list[str], available_peers: list[str], current_user: str, parent=None) -> None:
        super().__init__(parent)
        self.group_id = group_id
        self.group_name = group_name
        self.current_members = list(current_members)
        self.available_peers = list(available_peers)
        self.current_user = current_user
        
        # We need a reference to the main window to call peer_node
        self.main_window = parent

        self.setWindowTitle(f"Manage Group: {group_name}")
        self.setFixedSize(400, 500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title = QLabel(f"📁 Manage: {self.group_name}")
        title.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {COLORS['accent']};"
        )
        layout.addWidget(title)

        # ── Current Members ──
        lbl_current = QLabel("Current Members:")
        lbl_current.setStyleSheet(f"font-weight: bold; color: {COLORS['text_secondary']};")
        layout.addWidget(lbl_current)
        
        members_scroll = QScrollArea()
        members_scroll.setWidgetResizable(True)
        members_scroll.setStyleSheet("border: 1px solid #ccc;")

        members_widget = QWidget()
        self.members_layout = QVBoxLayout(members_widget)
        self.members_layout.setSpacing(6)
        
        self._populate_members()
        
        self.members_layout.addStretch()
        members_scroll.setWidget(members_widget)
        layout.addWidget(members_scroll, stretch=1)

        # Divider
        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {COLORS['border']}; margin: 8px 0;")
        layout.addWidget(divider)

        # ── Add Members ──
        lbl_add = QLabel("Add Online Peers:")
        lbl_add.setStyleSheet(f"font-weight: bold; color: {COLORS['text_secondary']};")
        layout.addWidget(lbl_add)
        
        add_scroll = QScrollArea()
        add_scroll.setWidgetResizable(True)
        add_scroll.setStyleSheet("border: 1px solid #ccc;")

        add_widget = QWidget()
        self.add_layout = QVBoxLayout(add_widget)
        self.add_layout.setSpacing(6)
        
        self._populate_add_peers()
        
        self.add_layout.addStretch()
        add_scroll.setWidget(add_widget)
        layout.addWidget(add_scroll, stretch=1)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                min-height: 38px;
                color: {COLORS['text_primary']};
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_hover']};
            }}
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _populate_members(self) -> None:
        # Clear layout first (except stretch)
        for i in reversed(range(self.members_layout.count() - 1)):
            widget = self.members_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                
        for member in sorted(self.current_members):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            
            name_label = QLabel(member)
            name_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 14px;")
            row_layout.addWidget(name_label)
            
            if member != self.current_user:
                remove_btn = QPushButton("Remove")
                remove_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {COLORS['error']};
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 4px 8px;
                    }}
                    QPushButton:hover {{
                        background-color: #d32f2f;
                    }}
                """)
                remove_btn.clicked.connect(lambda checked, m=member: self._on_remove(m))
                row_layout.addWidget(remove_btn)
                
            self.members_layout.insertWidget(self.members_layout.count() - 1, row)

    def _populate_add_peers(self) -> None:
        # Clear layout first (except stretch)
        for i in reversed(range(self.add_layout.count() - 1)):
            widget = self.add_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                
        peers_to_add = [p for p in self.available_peers if p not in self.current_members]
        
        if not peers_to_add:
            lbl = QLabel("No new online peers available.")
            lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-style: italic;")
            self.add_layout.insertWidget(self.add_layout.count() - 1, lbl)
            return

        for peer in sorted(peers_to_add):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            
            name_label = QLabel(peer)
            name_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 14px;")
            row_layout.addWidget(name_label)
            
            add_btn = QPushButton("Add")
            add_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['btn_bg']};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 8px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['btn_hover']};
                }}
            """)
            add_btn.clicked.connect(lambda checked, p=peer: self._on_add(p))
            row_layout.addWidget(add_btn)
            
            self.add_layout.insertWidget(self.add_layout.count() - 1, row)

    def _on_remove(self, member: str) -> None:
        reply = QMessageBox.question(
            self,
            "Confirm Remove",
            f"Are you sure you want to remove {member} from the group?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # We assume main_window has peer_node
            if self.main_window and hasattr(self.main_window, "peer_node"):
                asyncio.run_coroutine_threadsafe(
                    self.main_window.peer_node.remove_group_member(self.group_id, member),
                    self.main_window.loop
                )
            
            # Optimistically update the UI in the dialog
            if member in self.current_members:
                self.current_members.remove(member)
            self._populate_members()
            self._populate_add_peers()

    def _on_add(self, peer: str) -> None:
        if self.main_window and hasattr(self.main_window, "peer_node"):
            asyncio.run_coroutine_threadsafe(
                self.main_window.peer_node.add_group_member(self.group_id, peer),
                self.main_window.loop
            )
            
        # Optimistically update the UI in the dialog
        if peer not in self.current_members:
            self.current_members.append(peer)
        self._populate_members()
        self._populate_add_peers()
