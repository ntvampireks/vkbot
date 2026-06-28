"""Тесты для MessageQueue."""

import pytest
import threading
import time

from bot.services.message_queue import MessageQueue, QueuedMessage


class TestMessageQueue:
    """Тесты для MessageQueue."""

    def test_queue_creation(self):
        """Проверка создания очереди."""
        queue = MessageQueue()
        assert queue.qsize == 0

    def test_put(self):
        """Помещение сообщения в очередь."""
        queue = MessageQueue()
        queue.put(123, 'test')
        assert queue.qsize == 1

    def test_put_and_get(self):
        """Помещение и получение сообщения."""
        queue = MessageQueue()

        queue.put(123, 'Hello', reply_to=456)
        assert queue.qsize == 1

        message = queue.get(timeout=0.1)
        assert message is not None
        assert message.peer_id == 123
        assert message.text == 'Hello'
        assert message.reply_to == 456

    def test_get_timeout(self):
        """Таймаут при получении из пустой очереди."""
        queue = MessageQueue()

        message = queue.get(timeout=0.1)
        assert message is None

    def test_mark_done(self):
        """Пометка сообщения как обработанного."""
        queue = MessageQueue()

        queue.put(123, 'test')
        message = queue.get(timeout=0.1)
        assert message is not None

        queue.mark_done(message)
        # task_done() уменьшает unfinished_tasks

    def test_join(self):
        """Ожидание обработки всех сообщений в очереди."""
        queue = MessageQueue()

        queue.put(123, 'test')
        message = queue.get(timeout=0.1)
        assert message is not None

        queue.mark_done(message)
        queue.join()  # Должно завершиться сразу, так как очередь пуста

    def test_multiple_messages(self):
        """Обработка нескольких сообщений."""
        queue = MessageQueue()

        for i in range(5):
            queue.put(i, f'message_{i}')

        assert queue.qsize == 5

        messages = []
        while queue.qsize > 0:
            msg = queue.get(timeout=0.1)
            if msg:
                messages.append(msg)
                queue.mark_done(msg)

        assert len(messages) == 5

    def test_queued_message_namedtuple(self):
        """Проверка QueuedMessage NamedTuple."""
        message = QueuedMessage(peer_id=123, text='test', reply_to=456)
        assert message.peer_id == 123
        assert message.text == 'test'
        assert message.reply_to == 456

        # Доступ по индексам
        assert message[0] == 123
        assert message[1] == 'test'
        assert message[2] == 456

    def test_thread_safety(self):
        """Потокобезопасность очереди."""
        queue = MessageQueue()
        errors = []

        def producer():
            try:
                for i in range(100):
                    queue.put(i, f'msg_{i}')
            except Exception as e:
                errors.append(e)

        def consumer():
            try:
                for _ in range(100):
                    msg = queue.get(timeout=0.5)
                    if msg:
                        queue.mark_done(msg)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=producer),
            threading.Thread(target=consumer),
            threading.Thread(target=consumer),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_queue_maxsize(self):
        """Проверка ограничения размера очереди."""
        queue = MessageQueue(maxsize=2)

        queue.put(1, 'first')
        queue.put(2, 'second')
        assert queue.qsize == 2
