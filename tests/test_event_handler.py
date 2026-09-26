"""Тесты для EventHandler: фильтрация входящих событий VK."""
from unittest.mock import Mock

from vk_api.longpoll import VkEventType

from bot.core.event_handler import EventHandler


def make_settings() -> Mock:
    """Settings-заглушка: EventHandler читает только эти поля."""
    settings = Mock()
    settings.dedup_max_size = 1000
    settings.dedup_ttl_seconds = 300
    settings.per_user_max_requests = 10
    settings.per_user_window_seconds = 60
    settings.max_message_length = 10000
    settings.enable_prompt_injection_protection = True
    return settings


def make_event(message_id: int, peer_id: int, user_id: int) -> dict:
    """Сырое событие MESSAGE_NEW в формате, которое отдаёт VKClient._parse_event."""
    return {
        'type': VkEventType.MESSAGE_NEW,
        'message_id': message_id,
        'peer_id': peer_id,
        'user_id': user_id,
        'text': f'@Бот вопрос {message_id}',
        'timestamp': 1700000000,
        'attachments': [],
        'out': 0,
    }


class TestEventDeduplication:
    """Дедупликация не должна склеивать разные диалоги."""

    def test_same_message_id_from_different_dialogs_is_not_dropped(self):
        """message_id уникален только в пределах диалога, поэтому одинаковые
        message_id из разных диалогов — два разных сообщения."""
        received = []
        handler = EventHandler(
            on_message_callback=received.append,
            bot_user_id=None,
            settings=make_settings(),
            logger=Mock()
        )

        handler.handle_event(make_event(message_id=150, peer_id=2000000001, user_id=111))
        handler.handle_event(make_event(message_id=150, peer_id=2000000002, user_id=222))

        assert [message.user_id for message in received] == [111, 222]

    def test_replayed_event_is_dropped(self):
        """Replay после реконнекта LongPoll: тот же peer_id и тот же message_id
        — настоящий дубликат, он обязан отбрасываться."""
        received = []
        handler = EventHandler(
            on_message_callback=received.append,
            bot_user_id=None,
            settings=make_settings(),
            logger=Mock()
        )

        handler.handle_event(make_event(message_id=150, peer_id=2000000001, user_id=111))
        handler.handle_event(make_event(message_id=150, peer_id=2000000001, user_id=111))

        assert len(received) == 1
