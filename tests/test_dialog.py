"""Тесты для доменных моделей Dialog и Message."""
from datetime import datetime, timedelta
import pytest

from bot.domains.dialog import Dialog
from bot.domains.message import Message


class TestDialog:
    """Тесты для Dialog."""

    def test_create_dialog(self):
        """Создание диалога."""
        dialog = Dialog(user_id=123, last_active=datetime.now())
        assert dialog.user_id == 123
        assert dialog.state is None
        assert dialog.context == {}
        assert dialog.history == []

    def test_add_message_user(self):
        """Добавление сообщения от пользователя."""
        dialog = Dialog(user_id=123, last_active=datetime.now())
        dialog.add_message('user', 'привет')
        assert len(dialog.history) == 1
        assert dialog.history[0]['role'] == 'user'
        assert dialog.history[0]['text'] == 'привет'

    def test_add_message_bot(self):
        """Добавление сообщения от бота."""
        dialog = Dialog(user_id=123, last_active=datetime.now())
        dialog.add_message('bot', 'здравствуйте')
        assert dialog.history[0]['role'] == 'bot'
        assert dialog.history[0]['text'] == 'здравствуйте'

    def test_add_multiple_messages(self):
        """Добавление нескольких сообщений."""
        dialog = Dialog(user_id=123, last_active=datetime.now())
        dialog.add_message('user', 'привет')
        dialog.add_message('bot', 'здравствуйте')
        dialog.add_message('user', 'как дела?')
        assert len(dialog.history) == 3

    def test_history_limit(self):
        """История ограничивается 10 сообщениями."""
        dialog = Dialog(user_id=123, last_active=datetime.now())
        for i in range(15):
            dialog.add_message('user', f'сообщение {i}')
        assert len(dialog.history) == 10
        # Проверяем что старые сообщения удалены
        assert dialog.history[0]['text'] == 'сообщение 5'

    def test_is_active_within_timeout(self):
        """Диалог активен в пределах timeout."""
        dialog = Dialog(
            user_id=123,
            last_active=datetime.now() - timedelta(hours=1)
        )
        assert dialog.is_active(timeout_hours=24) is True

    def test_is_active_expired(self):
        """Диалог просрочен."""
        dialog = Dialog(
            user_id=123,
            last_active=datetime.now() - timedelta(hours=48)
        )
        assert dialog.is_active(timeout_hours=24) is False

    def test_is_active_exactly_at_timeout(self):
        """Диалог на границе timeout."""
        dialog = Dialog(
            user_id=123,
            last_active=datetime.now() - timedelta(hours=24, minutes=1)
        )
        assert dialog.is_active(timeout_hours=24) is False

    def test_dialog_with_state(self):
        """Диалог со state."""
        dialog = Dialog(
            user_id=123,
            last_active=datetime.now(),
            state='waiting_for_name'
        )
        assert dialog.state == 'waiting_for_name'

    def test_dialog_with_context(self):
        """Диалог с контекстом."""
        dialog = Dialog(
            user_id=123,
            last_active=datetime.now(),
            context={'step': 2, 'data': 'test'}
        )
        assert dialog.context['step'] == 2
        assert dialog.context['data'] == 'test'


class TestMessage:
    """Тесты для Message."""

    def test_create_message(self):
        """Создание сообщения."""
        message = Message(
            id=1,
            user_id=123,
            text="привет",
            timestamp=datetime.now()
        )
        assert message.id == 1
        assert message.user_id == 123
        assert message.text == "привет"

    def test_message_from_vk_event_basic(self):
        """Создание из VK события с базовыми полями."""
        event_data = {
            "message_id": 42,
            "user_id": 999,
            "text": "привет!",
            "timestamp": 1699900000,
            "peer_id": 100,
            "attachments": [],
            "out": 0
        }
        message = Message.from_vk_event(event_data)
        assert message.id == 42
        assert message.user_id == 999
        assert message.text == "привет!"

    def test_message_from_vk_event_with_attachments(self):
        """Создание из VK события с вложениями."""
        event_data = {
            "message_id": 42,
            "user_id": 999,
            "text": "посмотри фото",
            "timestamp": 1699900000,
            "peer_id": 100,
            "attachments": [{"type": "photo"}],
            "out": 0
        }
        message = Message.from_vk_event(event_data)
        assert len(message.attachments) == 1
        assert message.attachments[0]['type'] == 'photo'

    def test_message_from_vk_event_with_datetime_timestamp(self):
        """Создание из VK события с datetime timestamp."""
        ts = datetime(2024, 11, 14, 10, 30, 0)
        event_data = {
            "message_id": 42,
            "user_id": 999,
            "text": "привет",
            "timestamp": ts,
            "peer_id": 100,
            "attachments": [],
            "out": 0
        }
        message = Message.from_vk_event(event_data)
        assert message.timestamp == ts


class TestDialogThreadSafety:
    """Тесты на потокобезопасность Dialog."""

    def test_concurrent_add_message(self):
        """Параллельное добавление сообщений из нескольких потоков."""
        import threading
        import time

        # Большой лимит чтобы сообщения не обрезались
        dialog = Dialog(
            user_id=123,
            last_active=datetime.now(),
            max_history_messages=1000
        )

        num_threads = 10
        messages_per_thread = 20
        errors = []

        def add_messages(thread_id):
            try:
                for i in range(messages_per_thread):
                    dialog.add_message('user', f'msg_{thread_id}_{i}')
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=add_messages, args=(i,))
            for i in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Все сообщения должны быть добавлены без потерь
        expected_count = num_threads * messages_per_thread
        actual_count = len(dialog.history)

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert actual_count == expected_count, f"Expected {expected_count} messages, got {actual_count}"

    def test_concurrent_read_write(self):
        """Параллельное чтение и запись."""
        import threading

        dialog = Dialog(
            user_id=123,
            last_active=datetime.now(),
            max_history_messages=100
        )

        # Добавим начальные сообщения
        for i in range(10):
            dialog.add_message('user', f'init_{i}')

        errors = []
        read_counts = []

        def writer():
            try:
                for i in range(50):
                    dialog.add_message('bot', f'bot_msg_{i}')
            except Exception as e:
                errors.append(('writer', e))

        def reader(reader_id):
            try:
                for _ in range(50):
                    history = dialog.get_history()
                    read_counts.append(len(history))
            except Exception as e:
                errors.append((f'reader_{reader_id}', e))

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader, args=(1,)),
            threading.Thread(target=reader, args=(2,)),
            threading.Thread(target=reader, args=(3,)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(read_counts) == 150  # 3 читателя × 50 итераций
