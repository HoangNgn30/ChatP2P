"""
Entry point: Bootstrap / Tracker Server.

Usage::

    python run_bootstrap.py
    python run_bootstrap.py --host 0.0.0.0 --port 9000
"""

import argparse
import asyncio
import sys

from bootstrap_server.server import BootstrapServer
from database.db_connection import DatabaseConnection
from utils.config import Config
from utils.logger import get_logger

log = get_logger("bootstrap")


def parse_args():
    parser = argparse.ArgumentParser(description="P2P Chat – Bootstrap Server")
    parser.add_argument("--host", default=Config.BOOTSTRAP_HOST, help="Bind host")
    parser.add_argument(
        "--port", type=int, default=Config.BOOTSTRAP_PORT, help="Bind port"
    )
    return parser.parse_args()


async def main():
    args = parse_args()

    # Validate config
    problems = Config.validate()
    if problems:
        for p in problems:
            log.error("Config error: %s", p)
        sys.exit(1)

    # Connect to MongoDB
    db = DatabaseConnection.get_instance(Config.MONGODB_URI)

    # Start server
    server = BootstrapServer(args.host, args.port, db)

    try:
        await server.start()
    except KeyboardInterrupt:
        log.info("Shutting down …")
    finally:
        await server.stop()
        db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
