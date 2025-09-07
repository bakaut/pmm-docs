# Standard library imports
from typing import Optional

class ModerationService:
    """
    Сервис модерации пользователей.
    Отвечает за проверку нарушений и применение модерационных действий.
    """

    def __init__(self, database_manager, telegram_bot, logger):
        """
        Инициализация сервиса модерации.

        Args:
            database_manager: Менеджер базы данных
            telegram_bot: Телеграм бот для отправки сообщений
            logger: Логгер для записи событий
        """
        self.db = database_manager
        self.telegram_bot = telegram_bot
        self.logger = logger

    def moderate_user(self, chat_id: int, tg_user_id: str, additional_reason: str = "Нарушение правил") -> Optional[int]:
        """
        Модерация пользователя и отправка соответствующего сообщения в Telegram.

        Args:
            chat_id: ID чата в Telegram
            tg_user_id: ID пользователя в Telegram
            additional_reason: Дополнительная причина модерации

        Returns:
            Количество предупреждений пользователя (1 или 2) или None
        """
        self.logger.debug("Moderating user %s with reason: %s", tg_user_id, additional_reason)

        result = self.db.moderate_user(tg_user_id, additional_reason)

        if result == 1:
            # Первое предупреждение
            reason_msg = (
                f"Первое предупреждение, причина:\n- {additional_reason}\n"
                "Свобода ≠ вседозволенность. Ознакомьтесь с правилами:\n"
                "https://bit.ly/4j7AzIg\nПовторное предупреждение — бан навсегда."
            )
            self.telegram_bot.send_message_chunks(chat_id, reason_msg)
            self.logger.info("First warning sent to user %s", tg_user_id)

        elif result == 2:
            # Второе предупреждение → перманентный бан
            reason_msg = "Вы перемещены в Комнату Забвения, бан навсегда."
            self.telegram_bot.send_message_chunks(chat_id, reason_msg)
            self.logger.info("User %s permanently banned", tg_user_id)

        return result

    def is_user_blocked(self, tg_user_id: str) -> bool:
        """
        Проверка, заблокирован ли пользователь.

        Args:
            tg_user_id: ID пользователя в Telegram

        Returns:
            True если пользователь заблокирован, False иначе
        """
        user_mod_info = self.db.get_user_moderation_info(tg_user_id)
        is_blocked = user_mod_info["warnings"] > 2 and user_mod_info["blocked"]

        if is_blocked:
            self.logger.debug("User %s is blocked", tg_user_id)

        return is_blocked

    def get_user_moderation_status(self, tg_user_id: str) -> dict:
        """
        Получение статуса модерации пользователя.

        Args:
            tg_user_id: ID пользователя в Telegram

        Returns:
            Словарь с информацией о модерации пользователя
        """
        return self.db.get_user_moderation_info(tg_user_id)
