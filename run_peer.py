"""
Entry point: Peer Node with PyQt6 GUI.

Usage::

    python run_peer.py
    python run_peer.py --port 5002 --bootstrap-host 192.168.1.10 --bootstrap-port 9000
"""

import argparse
import asyncio
import socket
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from database.db_connection import DatabaseConnection
from gui.login_dialog import LoginDialog
from gui.main_window import MainWindow
from gui.styles import MAIN_STYLE
from peer.peer_node import PeerNode
from utils.config import Config
from utils.logger import get_logger

log = get_logger("peer")


def get_local_ip() -> str:
    """Best-effort detection of the local LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def parse_args():
    parser = argparse.ArgumentParser(description="P2P Chat – Peer Node")
    parser.add_argument("--host", default=None, help="Peer bind host (auto-detect)")
    parser.add_argument("--port", type=int, default=None, help="Peer listen port")
    parser.add_argument("--bootstrap-host", default=None, help="Bootstrap server host")
    parser.add_argument("--bootstrap-port", type=int, default=None, help="Bootstrap port")
    parser.add_argument("--username", default=None, help="Username (skips login dialog)")
    parser.add_argument("--password", default=None, help="Password (skips login dialog)")
    parser.add_argument("--register", action="store_true", help="Register new account")
    return parser.parse_args()


async def run_peer(
    app: QApplication,
    username: str,
    password: str,
    is_register: bool,
    peer_host: str,
    peer_port: int,
    bs_host: str,
    bs_port: int,
) -> None:
    """Core async routine: connect, authenticate, and show the main window."""
    # Connect to MongoDB
    try:
        db = DatabaseConnection.get_instance(Config.MONGODB_URI)
    except Exception as exc:
        QMessageBox.critical(None, "Database Error", f"Cannot connect to MongoDB:\n{exc}")
        return

    # Create peer node
    peer = PeerNode(username, peer_host, peer_port, db)
    await peer.start()

    # Connect to bootstrap
    connected = await peer.connect_to_bootstrap(bs_host, bs_port)
    if not connected:
        QMessageBox.critical(
            None, "Connection Error",
            f"Cannot connect to bootstrap server at {bs_host}:{bs_port}",
        )
        return

    # Authenticate
    if is_register:
        result = await peer.register(password)
    else:
        result = await peer.login(password)

    if result.get("status") != "success":
        QMessageBox.critical(
            None, "Authentication Error",
            result.get("message", "Authentication failed"),
        )
        await peer.disconnect()
        return

    log.info("Authenticated as %s – %s", username, result.get("message"))

    # Get the running event loop
    loop = asyncio.get_event_loop()

    # Show main window
    window = MainWindow(peer, loop)
    window.show()

    # Keep the app running
    while window.isVisible():
        await asyncio.sleep(0.05)
        app.processEvents()

    # Cleanup
    await peer.disconnect()
    db.close()


def main():
    args = parse_args()

    # Validate config
    problems = Config.validate()
    if problems:
        for p in problems:
            log.error("Config error: %s", p)
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setStyleSheet(MAIN_STYLE)

    # If CLI args provided, skip login dialog
    if args.username and args.password:
        username = args.username
        password = args.password
        is_register = args.register
        peer_host = args.host or get_local_ip()
        peer_port = args.port or Config.PEER_PORT
        bs_host = args.bootstrap_host or Config.BOOTSTRAP_HOST
        bs_port = args.bootstrap_port or Config.BOOTSTRAP_PORT
    else:
        # Show login dialog
        dialog = LoginDialog()
        if not dialog.exec():
            sys.exit(0)

        username = dialog.username
        password = dialog.password
        is_register = dialog.is_register
        peer_host = args.host or get_local_ip()
        peer_port = dialog.peer_port
        bs_host = dialog.bootstrap_host
        bs_port = dialog.bootstrap_port

    log.info(
        "Starting peer: %s @ %s:%d → bootstrap %s:%d",
        username, peer_host, peer_port, bs_host, bs_port,
    )

    # Run the async main loop
    try:
        asyncio.run(
            run_peer(app, username, password, is_register, peer_host, peer_port, bs_host, bs_port)
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
