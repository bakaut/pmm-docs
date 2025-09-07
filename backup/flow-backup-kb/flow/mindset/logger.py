# Standard library imports
import logging
from typing import Optional

# Third-party imports
from pythonjsonlogger import jsonlogger


class YcLoggingFormatter(jsonlogger.JsonFormatter):
    """Кастомный форматтер для логов в формате Yandex Cloud."""

    def add_fields(self, log_record, record, message_dict):
        super(YcLoggingFormatter, self).add_fields(log_record, record, message_dict)
        log_record['logger'] = record.name
        log_record['level'] = record.levelname.replace("WARNING", "WARN").replace("CRITICAL", "FATAL")


class YcLogger:
    """Класс для создания и настройки логера с кастомным форматированием."""

    def __init__(self, logger_name='MyLogger', log_level=logging.DEBUG):
        """
        Инициализация логера.

        Args:
            logger_name (str): Имя логера (по умолчанию 'MyLogger')
            log_level (int): Уровень логирования (по умолчанию logging.DEBUG)
        """
        self.logger_name = logger_name
        self.log_level = log_level
        self.logger = self._setup_logger()

    def _setup_logger(self):
        """Настройка и конфигурация логера."""
        logger = logging.getLogger(self.logger_name)
        logger.setLevel(self.log_level)
        logger.propagate = False

        # Очищаем существующие обработчики, чтобы избежать дублирования
        logger.handlers.clear()

        # Создаем консольный обработчик
        console_handler = logging.StreamHandler()
        console_formatter = YcLoggingFormatter('%(message)s %(level)s %(logger)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        return logger

    def get_logger(self):
        """Возвращает настроенный логер."""
        return self.logger

    def set_log_level(self, level):
        """Изменяет уровень логирования."""
        self.log_level = level
        self.logger.setLevel(level)


# ──────────────────────────
#  DEFAULT LOGGER FACTORY
# ──────────────────────────

def get_default_logger(name: Optional[str] = None, log_level: Optional[int] = None) -> logging.Logger:
    """
    Возвращает настроенный логгер для использования по умолчанию в проекте.

    Args:
        name: Имя логгера. Если None, используется 'poymoymir'
        log_level: Уровень логирования. Если None, используется DEBUG

    Returns:
        Настроенный логгер с YC форматированием
    """
    logger_name = name or 'poymoymir'
    level = log_level or logging.DEBUG

    yc_logger = YcLogger(logger_name, level)
    return yc_logger.get_logger()


# Глобальный логгер по умолчанию для быстрого импорта
default_logger = get_default_logger()
