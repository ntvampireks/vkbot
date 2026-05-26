from datetime import datetime

from bot.domains.dialog import Dialog
from bot.config import Config
from bot.utils.logger import setup_logger
import storage.db as db

logger = setup_logger(__name__)


class DialogService:
    def __init__(self):
        self.timeout_hours = Config.DIALOG_TIMEOUT_HOURS

    def get_dialog(self, user_id: int) -> Dialog | None:
        data = db.get_dialog(user_id)
        if not data:
            return None

        return Dialog(
            user_id=data['user_id'],
            last_active=data['last_active'],
            state=data['state'],
            context=data['context'],
            history=db.get_messages(user_id)
        )

    def save_dialog(self, dialog: Dialog):
        db.save_dialog(
            user_id=dialog.user_id,
            last_active=datetime.now(),
            state=dialog.state,
            context=dialog.context
        )

    def add_message(self, user_id: int, role: str, text: str):
        db.add_message(user_id, role, text)

    def is_session_active(self, dialog: Dialog) -> bool:
        return dialog.is_active(self.timeout_hours)
