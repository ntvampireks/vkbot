"""Тесты сетевого таймаута VKClient.

vk_api не передаёт timeout в requests (VkApi.method вызывает
self.http.post(url, values) без timeout), поэтому запрос с зависшим
соединением висит вечно. Таймаут задаётся сессией, которую VKClient
протягивает в VkApi(session=...).
"""

from unittest.mock import Mock, patch

import pytest
import requests
from vk_api.longpoll import Event, VkEventType, VkMessageFlag

from bot.config import Settings
from bot.core.vk_client import VKClient, TimeoutSession


def _mock_settings(api_timeout: int = 5) -> Mock:
    """Settings с значениями, нужными VKClient, без чтения .env."""
    settings = Mock(spec=Settings)
    settings.vk_group_token = 'token'
    settings.vk_group_id = '123'
    settings.vk_group_id_int = 123
    settings.max_message_length = 4096
    settings.message_api_timeout = api_timeout
    return settings


@pytest.fixture
def vk_client() -> VKClient:
    """VKClient без сетевых вызовов: VkApi и VkLongPoll заменены на mocks."""
    with patch('vk_api.VkApi'), patch('bot.core.vk_client.VkLongPoll'):
        return VKClient(_mock_settings(), Mock())


def _capture_requests(calls: list):
    """Подменяет requests.Session.request, записывая kwargs и не выходя в сеть."""
    def fake_request(self, method, url, **kwargs):
        calls.append({'method': method, 'url': url, **kwargs})
        raise requests.exceptions.ConnectionError('перехват до сети')
    return patch.object(requests.Session, 'request', fake_request)


def test_send_message_does_not_pass_timeout_to_vk_api(vk_client):
    """timeout — не параметр messages.send, в тело запроса он попадать не должен."""
    vk_client.send_message(123, 'текст')

    assert 'timeout' not in vk_client.vk.messages.send.call_args.kwargs


def test_vk_client_passes_session_with_api_timeout():
    """VKClient передал в VkApi сессию с таймаутом из settings.message_api_timeout."""
    with patch('vk_api.VkApi') as vkapi, patch('bot.core.vk_client.VkLongPoll'):
        VKClient(_mock_settings(api_timeout=7), Mock())

    session = vkapi.call_args.kwargs['session']
    assert session.default_timeout == 7


def test_send_message_uses_given_random_id(vk_client):
    """random_id из вызова уходит в VK API без изменений — это ключ идемпотентности."""
    vk_client.send_message(123, 'текст', random_id=42)

    assert vk_client.vk.messages.send.call_args.kwargs['random_id'] == 42


def test_send_message_generates_distinct_random_ids(vk_client):
    """random_id=None — значит генерировать, и для разных сообщений он разный."""
    vk_client.send_message(123, 'первое', random_id=None)
    first = vk_client.vk.messages.send.call_args_list[0].kwargs['random_id']

    vk_client.send_message(123, 'второе', random_id=None)
    second = vk_client.vk.messages.send.call_args_list[1].kwargs['random_id']

    assert isinstance(first, int)
    assert first != second


def test_session_applies_default_timeout_to_requests():
    """Запрос без явного timeout получает default_timeout."""
    calls: list = []
    with _capture_requests(calls):
        with pytest.raises(requests.exceptions.ConnectionError):
            TimeoutSession(default_timeout=7).post('https://api.vk.ru/method/messages.send', {'peer_id': 1})

    assert calls[0]['timeout'] == 7


def test_session_keeps_explicit_timeout():
    """Явный timeout в вызове не перезаписывается."""
    calls: list = []
    with _capture_requests(calls):
        with pytest.raises(requests.exceptions.ConnectionError):
            TimeoutSession(default_timeout=7).get('https://api.vk.ru/', timeout=1)

    assert calls[0]['timeout'] == 1


def _raw_message_new(peer_id: int, extra_values: dict | None = None, message_id: int = 77) -> Event:
    """Сырое MESSAGE_NEW: (type, message_id, flags, peer_id, timestamp, text, extra_values, ..., random_id).

    timestamp = 0: vk_api на ненулевом timestamp вызывает utcfromtimestamp,
    что даёт DeprecationWarning из библиотеки; время в этих тестах не проверяется.
    """
    return Event((VkEventType.MESSAGE_NEW, message_id, VkMessageFlag.UNREAD, peer_id,
                  0, 'текст', extra_values or {}, {}, 1))


def test_parse_event_keys_dialog_by_peer_id(vk_client):
    """Ключ диалога — peer_id: в беседе без from он не должен становиться -100."""
    chat_no_author = vk_client._parse_event(_raw_message_new(2000000001))
    assert chat_no_author['user_id'] == 2000000001
    assert chat_no_author['peer_id'] == 2000000001
    assert chat_no_author['author_id'] is None

    dm = vk_client._parse_event(_raw_message_new(444))
    assert dm['user_id'] == 444
    assert dm['author_id'] == 444


def test_parse_event_takes_chat_author_from_extra_values(vk_client):
    """В беседе автор берётся из extra_values['from'], но ключом диалога не становится."""
    chat = vk_client._parse_event(_raw_message_new(2000000001, {'from': '400'}))

    assert chat['author_id'] == 400
    assert chat['user_id'] == 2000000001
