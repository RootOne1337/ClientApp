import logging
import sys
from datetime import datetime
from pathlib import Path
from config import LOGS_DIR

# Формат логов
LOG_FORMAT = "%(asctime)s | %(levelname)-5s | %(message)s"
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
    
    # Файловый handler (DEBUG и выше)
    log_file = LOGS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)  # Changed to INFO for cleaner logs
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root_logger.addHandler(file_handler)
    
    # Возвращаем named logger
    logger = logging.getLogger(name)
    return logger


def get_logger(name: str = "virtbot") -> logging.Logger:
    """Получить логгер"""
    return logging.getLogger(name)
