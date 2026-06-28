import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / 'dialogs.db'


def _trim_old_messages(conn: sqlite3.Connection, user_id: int, max_messages: int) -> None:
    """Удалить старые сообщения, оставив только последние max_messages."""
    cursor = conn.execute(
        'SELECT id FROM messages WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?',
        (user_id, max_messages)
    )
    kept_ids = [row['id'] for row in cursor.fetchall()]
    if kept_ids:
        placeholders = ','.join(['?'] * len(kept_ids))
        query = 'DELETE FROM messages WHERE user_id = ? AND id NOT IN (' + placeholders + ')'
        conn.execute(query, (user_id, *kept_ids))
    else:
        conn.execute('DELETE FROM messages WHERE user_id = ?', (user_id,))


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        # Таблицы
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

        # Индексы для производительности
        conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_user_timestamp ON messages(user_id, timestamp)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_dialogs_last_active ON dialogs(last_active)')

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


def add_message(user_id: int, role: str, text: str, max_history_messages: int = 100) -> None:
    # Валидация входных данных
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError(f'user_id должен быть положительным целым числом, получен {user_id}')
    if not isinstance(role, str) or role not in ('user', 'bot'):
        raise ValueError(f'role должен быть "user" или "bot", получен {role!r}')
    if not isinstance(text, str) or not text.strip():
        raise ValueError('text должен быть непустой строкой')

    timestamp = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute('''
            INSERT INTO messages (user_id, role, text, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (user_id, role, text, timestamp))
        # Удаляем старые сообщения
        _trim_old_messages(conn, user_id, max_history_messages)
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
