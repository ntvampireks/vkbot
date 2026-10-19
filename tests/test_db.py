"""Тесты storage/db: схема и зачистка записей с невалидным ключом диалога."""

import aiosqlite
import pytest

from storage import db


async def _insert_garbage(db_path) -> None:
    """Заводит строки с ключом -100 — их оставляют беседы, где VK не прислал автора."""
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "INSERT INTO dialogs (user_id, last_active) VALUES (-100, '2026-01-01T00:00:00')"
        )
        await conn.execute(
            "INSERT INTO messages (user_id, role, text, timestamp) "
            "VALUES (-100, 'user', 'текст', '2026-01-01T00:00:00')"
        )
        await conn.commit()


async def _count(db_path, table: str, condition: str) -> int:
    async with aiosqlite.connect(db_path) as conn:
        async with conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {condition}") as cursor:
            return (await cursor.fetchone())[0]


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Временная БД вместо storage/dialogs.db."""
    path = tmp_path / 'dialogs.db'
    monkeypatch.setattr(db, 'DB_PATH', path)
    return path


@pytest.mark.asyncio
async def test_init_db_removes_non_positive_dialog_keys(db_path):
    """Повторный запуск приложения чистит мусорные диалоги и их сообщения."""
    await db._init_db_async()
    await _insert_garbage(db_path)
    await db._init_db_async()

    assert await _count(db_path, 'dialogs', 'user_id <= 0') == 0
    assert await _count(db_path, 'messages', 'user_id <= 0') == 0


@pytest.mark.asyncio
async def test_init_db_keeps_valid_dialogs(db_path):
    """Зачистка не должна задеть настоящие диалоги."""
    await db._init_db_async()
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "INSERT INTO dialogs (user_id, last_active) VALUES (444, '2026-01-01T00:00:00')"
        )
        await conn.commit()
    await db._init_db_async()

    assert await _count(db_path, 'dialogs', 'user_id = 444') == 1
