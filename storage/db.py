import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path


DB_PATH = Path(__file__).parent / 'dialogs.db'


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS dialogs (
                user_id INTEGER PRIMARY KEY,
                last_active TEXT NOT NULL,
                state TEXT,
                context_json TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES dialogs(user_id)
            )
        ''')
        conn.commit()


def save_dialog(user_id: int, last_active: datetime, state: str | None = None, context: dict | None = None):
    with get_connection() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO dialogs (user_id, last_active, state, context_json)
            VALUES (?, ?, ?, ?)
        ''', (
            user_id,
            last_active.isoformat(),
            state,
            json.dumps(context) if context else None
        ))
        conn.commit()


def get_dialog(user_id: int) -> dict | None:
    with get_connection() as conn:
        cursor = conn.execute(
            'SELECT * FROM dialogs WHERE user_id = ?',
            (user_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                'user_id': row['user_id'],
                'last_active': datetime.fromisoformat(row['last_active']),
                'state': row['state'],
                'context': json.loads(row['context_json']) if row['context_json'] else {}
            }
    return None


def add_message(user_id: int, role: str, text: str):
    timestamp = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute('''
            INSERT INTO messages (user_id, role, text, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (user_id, role, text, timestamp))
        # Удаляем старые сообщения, оставляем только последние 10
        conn.execute('''
            DELETE FROM messages
            WHERE id NOT IN (
                SELECT id FROM messages
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT 10
            )
            AND user_id = ?
        ''', (user_id, user_id))
        conn.commit()


def get_messages(user_id: int, limit: int = 10) -> list:
    with get_connection() as conn:
        cursor = conn.execute('''
            SELECT role, text, timestamp
            FROM messages
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (user_id, limit))
        return [
            {'role': row['role'], 'text': row['text'], 'timestamp': row['timestamp']}
            for row in reversed(cursor.fetchall())
        ]
