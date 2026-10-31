"""SQLite: saved searches and listing ids already sent."""

import sqlite3
from pathlib import Path


class Storage:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                max_price INTEGER
            );
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                lang TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS seen (
                search_id INTEGER NOT NULL,
                listing_id TEXT NOT NULL,
                PRIMARY KEY (search_id, listing_id)
            );
            """
        )

    def get_lang(self, chat_id: int) -> str:
        row = self.db.execute("SELECT lang FROM chats WHERE chat_id = ?", (chat_id,)).fetchone()
        return row[0] if row else "en"

    def set_lang(self, chat_id: int, lang: str) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO chats (chat_id, lang) VALUES (?, ?) "
                "ON CONFLICT(chat_id) DO UPDATE SET lang = excluded.lang",
                (chat_id, lang),
            )

    def add_search(self, chat_id: int, url: str, max_price: int | None) -> int:
        with self.db:
            cur = self.db.execute(
                "INSERT INTO searches (chat_id, url, max_price) VALUES (?, ?, ?)",
                (chat_id, url, max_price),
            )
        return cur.lastrowid

    def searches(self, chat_id: int | None = None) -> list[tuple[int, int, str, int | None]]:
        sql = "SELECT id, chat_id, url, max_price FROM searches"
        args: tuple = ()
        if chat_id is not None:
            sql += " WHERE chat_id = ?"
            args = (chat_id,)
        return self.db.execute(sql + " ORDER BY id", args).fetchall()

    def remove_search(self, chat_id: int, search_id: int) -> bool:
        with self.db:
            cur = self.db.execute(
                "DELETE FROM searches WHERE id = ? AND chat_id = ?", (search_id, chat_id)
            )
            if cur.rowcount:
                self.db.execute("DELETE FROM seen WHERE search_id = ?", (search_id,))
        return cur.rowcount > 0

    def new_ids(self, search_id: int, ids: list[str]) -> list[str]:
        """Mark ids as seen and return the ones that were not seen before."""
        fresh = []
        with self.db:
            for listing_id in ids:
                cur = self.db.execute(
                    "INSERT OR IGNORE INTO seen (search_id, listing_id) VALUES (?, ?)",
                    (search_id, listing_id),
                )
                if cur.rowcount:
                    fresh.append(listing_id)
        return fresh
