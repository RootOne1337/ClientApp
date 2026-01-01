import logging
import sys
import os
import platform
from datetime import datetime
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from config import LOGS_DIR

# Get machine name for logs
def get_machine_name() -> str:
    """Get machine name for logging (uses platform.node() for full name)"""
    # platform.node() returns full computer name (e.g. DESKTOP-IOPA6D8T1)
    # COMPUTERNAME can be truncated (e.g. DESKTOP-IOPA6D8)
    return platform.node()

MACHINE_NAME = get_machine_name()

# Формат логов with machine name
LOG_FORMAT = f"%(asctime)s | %(levelname)-5s | [{MACHINE_NAME}] | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(name: str = "virtbot") -> logging.Logger:
    """Настройка логгера с файловым выводом для всех модулей"""
    
    # Настраиваем root logger для всех модулей
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Очищаем handlers чтобы не дублировать
    if root_logger.handlers:
        root_logger.handlers.clear()
    
    # Консольный handler (INFO и выше)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root_logger.addHandler(console_handler)
    
    # Файловый handler с автоматической ротацией (INFO и выше)
    # Ротация происходит в полночь, хранятся файлы за последние 30 дней
    base_log_file = LOGS_DIR / "bot.log"
    file_handler = TimedRotatingFileHandler(
        filename=str(base_log_file),
        when='midnight',        # Ротация в полночь
        interval=1,             # Каждый день
        backupCount=30,         # Хранить 30 дней
        encoding='utf-8',
        utc=False               # Использовать локальное время
    )
    
    # Формат имени для ротированных файлов: bot.log.2026-01-01
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root_logger.addHandler(file_handler)
    
    # Возвращаем named logger
    logger = logging.getLogger(name)
    return logger


def get_logger(name: str = "virtbot") -> logging.Logger:
    """Получить логгер"""
    return logging.getLogger(name)
