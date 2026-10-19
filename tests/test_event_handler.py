"""Тесты для EventHandler: фильтрация входящих событий VK."""
from unittest.mock import Mock

from vk_api.longpoll import VkEventType

from bot.core.event_handler import EventHandler


def make_settings(max_requests: int = 10) -> Mock:
    """Settings-заглушка: EventHandler читает только эти поля."""
    settings = Mock()
    settings.dedup_max_size = 1000
    settings.dedup_ttl_seconds = 300
    settings.per_user_max_requests = max_requests
    settings.per_user_window_seconds = 60
    settings.max_message_length = 10000
    settings.enable_prompt_injection_protection = True
    return settings


def make_event(message_id: int, peer_id: int, author_id: int | None = None) -> dict:
    """Сырое событие MESSAGE_NEW в формате, которое отдаёт VKClient._parse_event.

    user_id — ключ диалога (peer_id), author_id — автор сообщения; в беседе VK
    отдаёт автора только через extra_values['from'], поэтому он может отсутствовать.
    """
    return {
        'type': VkEventType.MESSAGE_NEW,
        'message_id': message_id,
        'peer_id': peer_id,
        'user_id': peer_id,
        'author_id': author_id,
        'text': f'@Бот вопрос {message_id}',
        'timestamp': 1700000000,
        'attachments': [],
        'out': 0,
    }


def make_handler(received: list, max_requests: int = 10) -> EventHandler:
    return EventHandler(
        on_message_callback=received.append,
        bot_user_id=None,
        settings=make_settings(max_requests),
        logger=Mock()
    )


class TestEventDeduplication:
    """Дедупликация не должна склеивать разные диалоги."""

    def test_same_message_id_from_different_dialogs_is_not_dropped(self):
        """message_id уникален только в пределах диалога, поэтому одинаковые
        message_id из разных диалогов — два разных сообщения."""
        received = []
        handler = make_handler(received)

        handler.handle_event(make_event(message_id=150, peer_id=2000000001, author_id=111))
        handler.handle_event(make_event(message_id=150, peer_id=2000000002, author_id=222))

        assert [message.peer_id for message in received] == [2000000001, 2000000002]

    def test_replayed_event_is_dropped(self):
        """Replay после реконнекта LongPoll: тот же peer_id и тот же message_id
        — настоящий дубликат, он обязан отбрасываться."""
        received = []
        handler = make_handler(received)

        handler.handle_event(make_event(message_id=150, peer_id=2000000001, author_id=111))
        handler.handle_event(make_event(message_id=150, peer_id=2000000001, author_id=111))

        assert len(received) == 1


class TestPerUserRateLimit:
    """Лимит частоты — по автору, а не по диалогу."""

    def test_limit_is_per_author_in_chat(self):
        """Двое участников беседы не должны тратить один лимит друг друга."""
        received = []
        handler = make_handler(received, max_requests=1)

        handler.handle_event(make_event(message_id=1, peer_id=2000000001, author_id=111))
        handler.handle_event(make_event(message_id=2, peer_id=2000000001, author_id=222))

        assert len(received) == 2

    def test_limit_falls_back_to_dialog_when_author_unknown(self):
        """Без автора лимит всё равно разделяет разные диалоги, а не сливает их в один."""
        received = []
        handler = make_handler(received, max_requests=1)

        handler.handle_event(make_event(message_id=1, peer_id=2000000001))
        handler.handle_event(make_event(message_id=2, peer_id=2000000002))

        assert len(received) == 2


class TestEventValidation:
    """Событие без валидного peer_id обработчик не пропускает дальше."""

    def test_event_without_peer_id_is_dropped(self):
        received = []
        handler = make_handler(received)

        event = make_event(message_id=1, peer_id=2000000001, author_id=111)
        event['peer_id'] = 0
        handler.handle_event(event)

        assert received == []
