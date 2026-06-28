"""Тесты для PerUserRateLimiter."""

import time
import pytest
from bot.utils.per_user_limiter import PerUserRateLimiter


class TestPerUserRateLimiter:
    """Тесты для PerUserRateLimiter."""

    def test_initial_state(self):
        """Проверка начального состояния."""
        limiter = PerUserRateLimiter(max_requests=5, window_seconds=60)
        assert limiter.max_requests == 5
        assert limiter.window_seconds == 60
        assert limiter.get_remaining_requests(123) == 5

    def test_allows_requests_within_limit(self):
        """Разрешение запросов в пределах лимита."""
        limiter = PerUserRateLimiter(max_requests=3, window_seconds=60)

        assert limiter.is_allowed(123) is True
        limiter.record_request(123)

        assert limiter.is_allowed(123) is True
        limiter.record_request(123)

        assert limiter.is_allowed(123) is True
        limiter.record_request(123)

    def test_blocks_when_limit_exceeded(self):
        """Блокировка при превышении лимита."""
        limiter = PerUserRateLimiter(max_requests=2, window_seconds=60)

        limiter.record_request(123)
        limiter.record_request(123)

        assert limiter.is_allowed(123) is False

    def test_different_users_independent(self):
        """Независимость лимитов для разных пользователей."""
        limiter = PerUserRateLimiter(max_requests=2, window_seconds=60)

        limiter.record_request(123)
        limiter.record_request(123)

        # Пользователь 123 заблокирован
        assert limiter.is_allowed(123) is False

        # Пользователь 456 ещё не делал запросов
        assert limiter.is_allowed(456) is True

    def test_window_expiry(self):
        """Истечение временного окна."""
        limiter = PerUserRateLimiter(max_requests=2, window_seconds=1)

        limiter.record_request(123)
        limiter.record_request(123)

        assert limiter.is_allowed(123) is False

        # Ждём истечения окна
        time.sleep(1.1)

        assert limiter.is_allowed(123) is True

    def test_remaining_requests(self):
        """Проверка оставшихся запросов."""
        limiter = PerUserRateLimiter(max_requests=5, window_seconds=60)

        assert limiter.get_remaining_requests(123) == 5

        limiter.record_request(123)
        assert limiter.get_remaining_requests(123) == 4

        limiter.record_request(123)
        limiter.record_request(123)
        assert limiter.get_remaining_requests(123) == 2

    def test_wait_time_when_blocked(self):
        """Время ожидания при блокировке."""
        limiter = PerUserRateLimiter(max_requests=2, window_seconds=60)

        limiter.record_request(123)
        limiter.record_request(123)

        wait_time = limiter.get_wait_time(123)
        assert wait_time is not None
        assert 0 <= wait_time <= 60

    def test_wait_time_when_allowed(self):
        """Время ожидания когда запрос разрешён."""
        limiter = PerUserRateLimiter(max_requests=2, window_seconds=60)

        limiter.record_request(123)

        assert limiter.get_wait_time(123) is None

    def test_reset_user(self):
        """Сброс лимита для пользователя."""
        limiter = PerUserRateLimiter(max_requests=2, window_seconds=60)

        limiter.record_request(123)
        limiter.record_request(123)
        assert limiter.is_allowed(123) is False

        limiter.reset(123)

        assert limiter.is_allowed(123) is True
        assert limiter.get_remaining_requests(123) == 2

    def test_reset_all(self):
        """Сброс всех лимитов."""
        limiter = PerUserRateLimiter(max_requests=1, window_seconds=60)

        limiter.record_request(123)
        limiter.record_request(456)

        assert limiter.is_allowed(123) is False
        assert limiter.is_allowed(456) is False

        limiter.reset_all()

        assert limiter.is_allowed(123) is True
        assert limiter.is_allowed(456) is True

    def test_cleanup_old_entries(self):
        """Очистка старых записей."""
        limiter = PerUserRateLimiter(max_requests=10, window_seconds=1)

        limiter.record_request(123)
        limiter.record_request(456)

        time.sleep(1.1)

        removed = limiter.cleanup_old_entries()

        assert removed == 2
        assert len(limiter._user_requests) == 0

    def test_invalid_max_requests(self):
        """Ошибка при invalid max_requests."""
        with pytest.raises(ValueError):
            PerUserRateLimiter(max_requests=0, window_seconds=60)

        with pytest.raises(ValueError):
            PerUserRateLimiter(max_requests=-1, window_seconds=60)

    def test_invalid_window_seconds(self):
        """Ошибка при invalid window_seconds."""
        with pytest.raises(ValueError):
            PerUserRateLimiter(max_requests=10, window_seconds=0)

        with pytest.raises(ValueError):
            PerUserRateLimiter(max_requests=10, window_seconds=-1)

    def test_thread_safety(self):
        """Потокобезопасность."""
        import threading

        limiter = PerUserRateLimiter(max_requests=100, window_seconds=60)
        results = []

        def make_requests(user_id: int, count: int):
            allowed = 0
            for _ in range(count):
                if limiter.is_allowed(user_id):
                    limiter.record_request(user_id)
                    allowed += 1
            results.append(allowed)

        threads = [
            threading.Thread(target=make_requests, args=(123, 50))
            for _ in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Все 5 потоков работают с одним user_id, максимум 100 запросов
        total_allowed = sum(results)
        assert total_allowed <= 100

    def test_empty_user_requests_not_stored(self):
        """Пустые записи пользователей не хранятся."""
        limiter = PerUserRateLimiter(max_requests=1, window_seconds=1)

        limiter.record_request(123)
        assert 123 in limiter._user_requests

        time.sleep(1.1)
        limiter.cleanup_old_entries()

        assert 123 not in limiter._user_requests
