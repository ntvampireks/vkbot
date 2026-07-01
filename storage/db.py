"""Доступ к SQLite через aiosqlite."""

import asyncio
import aiosqlite
import json
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / 'dialogs.db'


async def _trim_old_messages(conn: aiosqlite.Connection, user_id: int, max_messages: int) -> None:
    """Удалить старые сообщения, оставив только последние max_messages."""
    cursor = await conn.execute(
        'SELECT id FROM messages WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?',
        (user_id, max_messages)
    )
    kept_ids = [row[0] for row in await cursor.fetchall()]
    if kept_ids:
        placeholders = ','.join(['?'] * len(kept_ids))
        query = 'DELETE FROM messages WHERE user_id = ? AND id NOT IN (' + placeholders + ')'
        await conn.execute(query, (user_id, *kept_ids))
    else:
        await conn.execute('DELETE FROM messages WHERE user_id = ?', (user_id,))


def init_db():
    """Инициализировать базу данных (синхронная обёртка)."""
    asyncio.run(_init_db_async())


async def _init_db_async():
    """Инициализировать базу данных (асинхронно)."""
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as conn:
        # Таблицы
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS dialogs (
                user_id INTEGER PRIMARY KEY,
                last_active TEXT NOT NULL,
                state TEXT,
                context_json TEXT
            )
        ''')
        await conn.execute('''
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
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_user_timestamp ON messages(user_id, timestamp)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_dialogs_last_active ON dialogs(last_active)')

        await conn.commit()


async def save_dialog(user_id: int, last_active: datetime, state: str | None = None, context: dict | None = None):
    """Сохранить диалог в БД (асинхронно)."""
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as conn:
        await conn.execute('''
            INSERT OR REPLACE INTO dialogs (user_id, last_active, state, context_json)
            VALUES (?, ?, ?, ?)
        ''', (
            user_id,
            last_active.isoformat(),
            state,
            json.dumps(context) if context else None
        ))
        await conn.commit()


async def get_dialog(user_id: int) -> dict | None:
    """Получить диалог пользователя из БД (асинхронно)."""
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            'SELECT * FROM dialogs WHERE user_id = ?',
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            return {
                'user_id': row[0],
                'last_active': datetime.fromisoformat(row[1]),
                'state': row[2],
                'context': json.loads(row[3]) if row[3] else {}
            }
    return None


async def add_message(user_id: int, role: str, text: str, max_history_messages: int = 100) -> None:
    """Добавить сообщение в диалог (асинхронно)."""
    # Валидация входных данных
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError(f'user_id должен быть положительным целым числом, получен {user_id}')
    if not isinstance(role, str) or role not in ('user', 'bot'):
        raise ValueError(f'role должен быть "user" или "bot", получен {role!r}')
    if not isinstance(text, str) or not text.strip():
        raise ValueError('text должен быть непустой строкой')

    timestamp = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as conn:
        await conn.execute('''
            INSERT INTO messages (user_id, role, text, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (user_id, role, text, timestamp))
        # Удаляем старые сообщения
        await _trim_old_messages(conn, user_id, max_history_messages)
        await conn.commit()


async def get_messages(user_id: int, limit: int = 10) -> list:
    """Получить последние сообщения пользователя (асинхронно)."""
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute('''
            SELECT role, text, timestamp
            FROM messages
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (user_id, limit))
        rows = await cursor.fetchall()
        return [
            {'role': row['role'], 'text': row['text'], 'timestamp': row['timestamp']}
            for row in reversed(rows)
        ]
