import sqlite3
import pytest
from analytics.db import _create_tables


@pytest.fixture()
def db_conn():
    """In-memory SQLite connection with schema applied."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _create_tables(conn)
    yield conn
    conn.close()
