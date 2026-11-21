"""Adds free data to options: what the action needs beyond the columns."""

import sqlite3


def up(conn: sqlite3.Connection) -> None:
    conn.execute("ALTER TABLE options ADD COLUMN data TEXT")
