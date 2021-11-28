"""Simple CLI for managing Postgres databases in Flask."""
from .config import init_db_callback
from .ops import create_db
from .ops import drop_db
from .types import PostgresUri

__version__ = "0.2.0"
