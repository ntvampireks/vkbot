import threading
import asyncio
from collections import OrderedDict
from datetime import datetime
from time import time
from typing import Dict, Tuple
import logging

from bot.domains.dialog import Dialog
from bot.config import Settings
from bot.utils.inject import get_default_logger
import storage.db as db

# Тип для кэша: user_id -> (Dialog, last_used_timestamp)
DialogCacheEntry = Tuple[Dialog, float]


class DialogService:
    """Сервис управления диалогами с LRU-кэшированием.

    Управляет контекстом диалогов пользователей, сохраняет историю сообщений
    в SQLite и поддерживает кэш активных диалогов в памяти.
    """

    def __init__(self, settings: Settings, logger: logging.Logger):
        """Инициализирует сервис диалогов.

        Args:
            settings: Конфигурация бота
            logger: Логгер
        """
        self._settings = settings
        self._logger = logger
        self.timeout_hours = self._settings.dialog_timeout_hours
        self.max_history_messages = self._settings.max_history_messages
        self.max_dialogs_cache = self._settings.max_dialogs_cache

        # OrderedDict для LRU-кэша: user_id -> (Dialog, last_used_timestamp)
        self._dialogs: OrderedDict[int, DialogCacheEntry] = OrderedDict()
        self._lock = threading.Lock()

    def _cleanup_old_dialogs(self) -> int:
        """Удаляет неактивные диалоги старше timeout_hours.

        Returns:
            Количество удалённых диалогов
        """
        now = time()
        timeout_seconds = self.timeout_hours * 3600
        removed = 0

        # Проходим с начала (старые записи в OrderedDict)
        for user_id, (_, last_used) in list(self._dialogs.items()):
            if now - last_used > timeout_seconds:
                del self._dialogs[user_id]
                removed += 1

        if removed > 0:
            self._logger.debug(f'Очищено {removed} неактивных диалогов (timeout: {self.timeout_hours}ч)')

        return removed

    def _trim_to_max_size(self) -> int:
        """Удаляет наименее используемые диалоги при превышении лимита.

        Returns:
            Количество удалённых диалогов
        """
        removed = 0

        while len(self._dialogs) > self.max_dialogs_cache:
            # popitem(last=False) удаляет oldest (первую запись)
            user_id, _ = self._dialogs.popitem(last=False)
            removed += 1
            self._logger.debug(f'Удалён диалог {user_id} из кэша (лимит: {self.max_dialogs_cache})')

        if removed > 0:
            self._logger.debug(f'Подстриг кэш до {self.max_dialogs_cache}: удалено {removed} диалогов')

        return removed

    async def get_dialog_async(self, user_id: int) -> Dialog | None:
        """Получает диалог пользователя.

        Сначала проверяет кэш, при отсутствии загружает из БД.

        Args:
            user_id: ID пользователя

        Returns:
            Диалог пользователя или None если не найден
        """
        with self._lock:
            if user_id in self._dialogs:
                # Обновляем last_used и перемещаем в конец (активный)
                dialog, _ = self._dialogs[user_id]
                self._dialogs[user_id] = (dialog, time())
                self._dialogs.move_to_end(user_id)
                return dialog

        # Чтение из БД вне блокировки (асинхронно)
        data = await db.get_dialog(user_id)
        if not data:
            return None

        dialog = Dialog(
            user_id=data['user_id'],
            last_active=data['last_active'],
            state=data['state'],
            context=data['context'],
            history=await db.get_messages(user_id),
            max_history_messages=self.max_history_messages
        )

        with self._lock:
            self._dialogs[user_id] = (dialog, time())
            self._trim_to_max_size()

        return dialog

    async def save_dialog_async(self, dialog: Dialog):
        """Сохраняет диалог в БД.

        Args:
            dialog: Диалог для сохранения
        """
        await db.save_dialog(
            user_id=dialog.user_id,
            last_active=dialog.last_active,
            state=dialog.state,
            context=dialog.context
        )

    async def add_message_async(self, user_id: int, role: str, text: str) -> None:
        """Добавляет сообщение в диалог.

        Сохраняет сообщение в БД и синхронизирует с кэшем.

        Args:
            user_id: ID пользователя
            role: Роль (user или bot)
            text: Текст сообщения
        """
        await db.add_message(user_id, role, text, self.max_history_messages)
        # Синхронизировать с кэшем в памяти
        with self._lock:
            if user_id in self._dialogs:
                dialog, _ = self._dialogs[user_id]
                dialog.add_message(role, text)
                # Обновляем last_used
                self._dialogs[user_id] = (dialog, time())

    def register_dialog(self, dialog: Dialog) -> None:
        """Регистрирует новый диалог в кэше.

        Args:
            dialog: Диалог для регистрации
        """
        with self._lock:
            self._dialogs[dialog.user_id] = (dialog, time())
            self._trim_to_max_size()