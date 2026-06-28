"""Очередь сообщений без фонового потока."""

from queue import Queue, Empty
from typing import NamedTuple


class QueuedMessage(NamedTuple):
    """Сообщение в очереди."""
    peer_id: int
    text: str
    reply_to: int | None


class MessageQueue:
    """Очередь сообщений без фоновой обработки.

    Отвечает только за хранение и извлечение сообщений.
    Не содержит логики отправки или фоновых потоков.
    """

    def __init__(self, maxsize: int = 0):
        """Инициализация очереди.

        Args:
            maxsize: Максимальный размер очереди (0 — без ограничения)
        """
        self._queue: Queue = Queue(maxsize=maxsize)

    def put(self, peer_id: int, text: str, reply_to: int | None = None) -> None:
        """Поместить сообщение в очередь.

        Args:
            peer_id: ID получателя
            text: Текст сообщения
            reply_to: ID сообщения, на которое ответить
        """
        self._queue.put((peer_id, text, reply_to))

    def get(self, timeout: float = 1.0) -> QueuedMessage | None:
        """Получить сообщение из очереди.

        Args:
            timeout: Время ожидания в секундах

        Returns:
            QueuedMessage или None если таймаут
        """
        try:
            peer_id, text, reply_to = self._queue.get(timeout=timeout)
            return QueuedMessage(peer_id, text, reply_to)
        except Empty:
            return None

    def mark_done(self, message: QueuedMessage) -> None:
        """Пометить сообщение как обработанное.

        Args:
            message: Обработанное сообщение
        """
        self._queue.task_done()

    def join(self) -> None:
        """Дождаться обработки всех сообщений в очереди."""
        self._queue.join()

    @property
    def qsize(self) -> int:
        """Получить размер очереди."""
        return self._queue.qsize()
