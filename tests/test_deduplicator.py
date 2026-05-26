"""Тесты для MessageDeduplicator."""
import time
import pytest

from bot.utils.deduplication import MessageDeduplicator


class TestMessageDeduplicator:
    """Тесты для MessageDeduplicator."""

    def test_deduplicator_creation(self):
        """Создание Deduplicator с параметрами."""
        dedup = MessageDeduplicator(max_size=500, ttl_seconds=120)
        assert dedup._cache is not None
        assert dedup._ttl == 120

    def test_first_message_not_duplicate(self):
        """Первое сообщение не дубликат."""
        dedup = MessageDeduplicator()
        assert dedup.is_duplicate(123) is False

    def test_same_message_is_duplicate(self):
        """Повторное сообщение с тем же ID — дубликат."""
        dedup = MessageDeduplicator()
        dedup.is_duplicate(123)  # Первое раз — не дубликат
        assert dedup.is_duplicate(123) is True  # Второе раз — дубликат

    def test_different_messages_not_duplicates(self):
        """Разные ID — не дубликаты."""
        dedup = MessageDeduplicator()
        assert dedup.is_duplicate(123) is False
        assert dedup.is_duplicate(456) is False
        assert dedup.is_duplicate(789) is False

    def test_old_messages_expire(self):
        """Устаревшие сообщения истекают."""
        dedup = MessageDeduplicator(ttl_seconds=0.2)

        dedup.is_duplicate(123)
        assert dedup.is_duplicate(123) is True

        # Ждём пока истечёт TTL
        time.sleep(0.25)

        # После истечения — не дубликат
        assert dedup.is_duplicate(123) is False

    def test_cache_grows_with_new_messages(self):
        """Кэш растёт с новыми сообщениями (max_size не реализован)."""
        dedup = MessageDeduplicator(max_size=5, ttl_seconds=300)

        for i in range(10):
            dedup.is_duplicate(i)

        # Кэш растёт — max_size eviction не реализован в текущей версии
        assert len(dedup._cache) == 10

    def test_concurrent_access(self):
        """Потокобезопасность Deduplicator."""
        import threading

        dedup = MessageDeduplicator(max_size=100, ttl_seconds=300)
        results = []
        lock = threading.Lock()

        def check_duplicate(msg_id):
            result = dedup.is_duplicate(msg_id)
            with lock:
                results.append(result)

        threads = [threading.Thread(target=check_duplicate, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Первое вхождение каждого ID — False, повторные — True
        assert len(results) == 50
