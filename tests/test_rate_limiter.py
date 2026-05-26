"""Тесты для RateLimiter."""
import time
import pytest

from bot.services.rate_limiter import RateLimiter


class TestRateLimiter:
    """Тесты для RateLimiter."""

    def test_limiter_creation(self):
        """Создание RateLimiter с параметрами."""
        limiter = RateLimiter(max_requests=5, period=2.0)
        assert limiter.max_requests == 5
        assert limiter.period == 2.0
        assert len(limiter.requests) == 0

    def test_allows_up_to_max_requests(self):
        """Разрешает до max_requests без задержки."""
        limiter = RateLimiter(max_requests=3, period=1.0)

        # Первые 3 запроса должны пройти сразу
        limiter.wait_if_needed()
        limiter.wait_if_needed()
        limiter.wait_if_needed()

        assert len(limiter.requests) == 3

    def test_waits_after_max_requests(self):
        """Ждёт после достижения лимита."""
        limiter = RateLimiter(max_requests=2, period=0.5)

        limiter.wait_if_needed()
        limiter.wait_if_needed()

        # 3-й запрос должен ждать
        start = time.time()
        limiter.wait_if_needed()
        elapsed = time.time() - start

        assert elapsed >= 0.4  # Должно ждать почти 0.5 сек

    def test_requests_expire_after_period(self):
        """Запросы истекают после периода."""
        limiter = RateLimiter(max_requests=2, period=0.3)

        limiter.wait_if_needed()
        limiter.wait_if_needed()
        assert len(limiter.requests) == 2

        # Ждём пока запросы истекут
        time.sleep(0.35)

        # После истечения должен разрешить новые запросы
        limiter.wait_if_needed()
        # Должно быть меньше старых запросов
        assert len(limiter.requests) <= 2

    def test_thread_safety(self):
        """Потокобезопасность RateLimiter."""
        import threading

        limiter = RateLimiter(max_requests=10, period=1.0)
        results = []

        def make_request():
            limiter.wait_if_needed()
            results.append(time.time())

        threads = [threading.Thread(target=make_request) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 20
