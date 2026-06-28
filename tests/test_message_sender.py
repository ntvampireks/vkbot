"""Тесты для MessageSender."""

import pytest
import threading
import time
from unittest.mock import Mock, MagicMock, patch
from unittest.mock import call

from bot.config import Settings
from bot.services.message_sender import MessageSender
from bot.services.message_queue import MessageQueue, QueuedMessage
from bot.services.rate_limiter import RateLimiter


def _create_mock_settings():
    """Создаёт mock Settings с дефолтными значениями."""
    settings = Mock(spec=Settings)
    settings.message_send_delay = 0
    settings.message_retry_delay = 0
    settings.message_api_timeout = 5
    return settings


class TestMessageSender:
    """Тесты для MessageSender."""

    def test_sender_creation(self):
        """Проверка создания отправителя."""
        vk_client = Mock()
        rate_limiter = RateLimiter()
        queue = MessageQueue()
        settings = _create_mock_settings()

        sender = MessageSender(
            vk_client=vk_client,
            rate_limiter=rate_limiter,
            queue=queue,
            settings=settings,
            max_retries=3
        )

        assert sender.vk_client == vk_client
        assert sender.rate_limiter == rate_limiter
        assert sender.queue == queue
        assert sender.max_retries == 3
        assert sender.is_running is False

    def test_start_and_stop(self):
        """Запуск и остановка фонового потока."""
        vk_client = Mock()
        rate_limiter = RateLimiter()
        queue = MessageQueue()
        settings = _create_mock_settings()

        sender = MessageSender(
            vk_client=vk_client,
            rate_limiter=rate_limiter,
            queue=queue,
            settings=settings,
            max_retries=3
        )

        assert sender.is_running is False
        sender.start()
        assert sender.is_running is True
        assert sender._worker_thread is not None
        assert sender._worker_thread.is_alive()

        sender.stop(timeout=1.0)
        assert sender.is_running is False

    def test_background_processing(self):
        """Фоновая обработка очереди."""
        vk_client = Mock()
        rate_limiter = RateLimiter()
        queue = MessageQueue()
        settings = _create_mock_settings()

        sender = MessageSender(
            vk_client=vk_client,
            rate_limiter=rate_limiter,
            queue=queue,
            settings=settings,
            max_retries=3
        )

        sender.start()

        # Поместить сообщение в очередь
        queue.put(123, 'Hello')

        # Дождаться обработки
        time.sleep(0.5)

        # Проверить что сообщение было отправлено
        assert vk_client.send_message.call_count >= 1

        sender.stop(timeout=2.0)

    def test_error_in_background_processing(self):
        """Обработка ошибки в фоновом потоке."""
        vk_client = Mock()
        vk_client.send_message.side_effect = Exception('Network error')

        rate_limiter = RateLimiter()
        queue = MessageQueue()
        settings = _create_mock_settings()

        sender = MessageSender(
            vk_client=vk_client,
            rate_limiter=rate_limiter,
            queue=queue,
            settings=settings,
            max_retries=1
        )

        sender.start()

        # Поместить сообщение в очередь
        queue.put(123, 'Hello')

        # Дождаться обработки
        time.sleep(0.5)

        sender.stop(timeout=2.0)

        # Ошибка должна была быть залогирована, но не должна заблокировать поток


class TestMessageSenderRetryLogic:
    """Тесты для retry-логики MessageSender."""

    def test_send_success_on_first_attempt(self):
        """Успешная отправка с первой попытки."""
        vk_client = Mock()
        rate_limiter = RateLimiter()
        queue = MessageQueue()
        settings = _create_mock_settings()

        sender = MessageSender(
            vk_client=vk_client,
            rate_limiter=rate_limiter,
            queue=queue,
            settings=settings,
            max_retries=3
        )

        message = QueuedMessage(peer_id=123, text='Hello', reply_to=None)

        sender._send_with_retry(message)

        # Успех с первой попытки — только один вызов
        assert vk_client.send_message.call_count == 1

    def test_send_success_on_second_attempt(self):
        """Успешная отправка со второй попытки."""
        vk_client = Mock()
        vk_client.send_message.side_effect = [
            Exception('Temporary error'),  # Первая попытка — ошибка
            None  # Вторая попытка — успех
        ]

        rate_limiter = RateLimiter()
        queue = MessageQueue()
        settings = _create_mock_settings()

        sender = MessageSender(
            vk_client=vk_client,
            rate_limiter=rate_limiter,
            queue=queue,
            settings=settings,
            max_retries=3
        )

        message = QueuedMessage(peer_id=123, text='Hello', reply_to=None)

        # Должно бросить последнее исключение после успеха
        # (логика в _send_with_retry: если успех — return, если все попытки исчерпаны — raise)
        sender._send_with_retry(message)

        # Успех на второй попытке — два вызова
        assert vk_client.send_message.call_count == 2

    def test_send_success_on_third_attempt(self):
        """Успешная отправка с третьей попытки."""
        vk_client = Mock()
        vk_client.send_message.side_effect = [
            Exception('Error 1'),
            Exception('Error 2'),
            None  # Третья попытка — успех
        ]

        rate_limiter = RateLimiter()
        queue = MessageQueue()
        settings = _create_mock_settings()

        sender = MessageSender(
            vk_client=vk_client,
            rate_limiter=rate_limiter,
            queue=queue,
            settings=settings,
            max_retries=3
        )

        message = QueuedMessage(peer_id=123, text='Hello', reply_to=None)

        sender._send_with_retry(message)

        # Успех на третьей попытке — три вызова
        assert vk_client.send_message.call_count == 3

    def test_send_fails_after_max_retries(self):
        """Ошибка после исчерпания всех попыток retry."""
        vk_client = Mock()
        vk_client.send_message.side_effect = Exception('Always fails')

        rate_limiter = RateLimiter()
        queue = MessageQueue()
        settings = _create_mock_settings()

        sender = MessageSender(
            vk_client=vk_client,
            rate_limiter=rate_limiter,
            queue=queue,
            settings=settings,
            max_retries=3
        )

        message = QueuedMessage(peer_id=123, text='Hello', reply_to=None)

        # Должно бросить исключение после исчерпания попыток
        with pytest.raises(Exception, match='Always fails'):
            sender._send_with_retry(message)

        # Должно быть ровно max_retries попыток
        assert vk_client.send_message.call_count == 3

    def test_send_fails_after_max_retries_with_custom_retries(self):
        """Ошибка после исчерпания 5 попыток retry."""
        vk_client = Mock()
        vk_client.send_message.side_effect = Exception('Network error')

        rate_limiter = RateLimiter()
        queue = MessageQueue()
        settings = _create_mock_settings()

        sender = MessageSender(
            vk_client=vk_client,
            rate_limiter=rate_limiter,
            queue=queue,
            settings=settings,
            max_retries=5
        )

        message = QueuedMessage(peer_id=123, text='Hello', reply_to=None)

        with pytest.raises(Exception, match='Network error'):
            sender._send_with_retry(message)

        # Должно быть ровно 5 попыток
        assert vk_client.send_message.call_count == 5

    def test_retry_delay_is_used(self):
        """Проверка что retry_delay используется между попытками."""
        vk_client = Mock()
        vk_client.send_message.side_effect = [
            Exception('Error 1'),
            Exception('Error 2'),
            None  # Успех на третьей попытке
        ]

        rate_limiter = RateLimiter()
        queue = MessageQueue()
        settings = _create_mock_settings()
        settings.message_retry_delay = 0.1  # 100ms задержка

        sender = MessageSender(
            vk_client=vk_client,
            rate_limiter=rate_limiter,
            queue=queue,
            settings=settings,
            max_retries=3
        )

        start_time = time.time()
        message = QueuedMessage(peer_id=123, text='Hello', reply_to=None)
        sender._send_with_retry(message)
        elapsed = time.time() - start_time

        # Должно быть 2 задержки между 3 попытками (после 1-й и после 2-й)
        # 2 * 0.1s = 0.2s минимум
        assert elapsed >= 0.15, f'Ожидалась задержка retry_delay, но прошло только {elapsed:.2f}s'

    def test_send_with_reply_to(self):
        """Проверка отправки с reply_to параметром."""
        vk_client = Mock()
        rate_limiter = RateLimiter()
        queue = MessageQueue()
        settings = _create_mock_settings()

        sender = MessageSender(
            vk_client=vk_client,
            rate_limiter=rate_limiter,
            queue=queue,
            settings=settings,
            max_retries=3
        )

        message = QueuedMessage(peer_id=123, text='Hello', reply_to=456)

        sender._send_with_retry(message)

        # Проверить что reply_to передан корректно
        vk_client.send_message.assert_called_once_with(
            123, 'Hello',
            reply_to=456,
            timeout=5
        )

    def test_send_with_custom_timeout(self):
        """Проверка отправки с кастомным таймаутом."""
        vk_client = Mock()
        rate_limiter = RateLimiter()
        queue = MessageQueue()
        settings = _create_mock_settings()
        settings.message_api_timeout = 10

        sender = MessageSender(
            vk_client=vk_client,
            rate_limiter=rate_limiter,
            queue=queue,
            settings=settings,
            max_retries=3
        )

        message = QueuedMessage(peer_id=123, text='Hello', reply_to=None)

        sender._send_with_retry(message)

        # Проверить что timeout передан корректно
        vk_client.send_message.assert_called_once_with(
            123, 'Hello',
            reply_to=None,
            timeout=10
        )
