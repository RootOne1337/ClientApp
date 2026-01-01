import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

# Определяем корень приложения
# Для .py: папка где лежит скрипт
# Для .exe (frozen): папка где лежит exe
if getattr(sys, 'frozen', False):
    # Скомпилированный exe
    APP_DIR = Path(sys.executable).parent.absolute()
else:
    # Обычный Python
    APP_DIR = Path(__file__).parent.absolute()

# Директории
DATA_DIR = APP_DIR / "data"
LOGS_DIR = APP_DIR / "logs"
SCREENSHOTS_DIR = APP_DIR / "screenshots"
SCRIPTS_DIR = APP_DIR / "scripts"

# Создаём директории
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
SCREENSHOTS_DIR.mkdir(exist_ok=True)

# Файлы данных (секретные, не в git)
ACCOUNT_FILE = DATA_DIR / "account.json"       # Данные аккаунта от API
CREDENTIALS_FILE = DATA_DIR / "credentials.json"  # Google credentials
STATE_FILE = DATA_DIR / "state.json"           # Game state (server, char, started_at)
STATE_FILE = DATA_DIR / "state.json"           # Состояние бота


class Settings:
    # Directories
    APP_DIR: Path = APP_DIR
    DATA_DIR: Path = DATA_DIR
    LOGS_DIR: Path = LOGS_DIR
    SCREENSHOTS_DIR: Path = SCREENSHOTS_DIR
    SCRIPTS_DIR: Path = SCRIPTS_DIR
    
    # API сервера VirtApp
    API_URL: str = os.getenv("API_URL", "http://gta5rp.leetpc.com/api")
    
    # API для получения конфига аккаунта (теперь на нашем сервере)
    CONFIG_API_URL: str = os.getenv("CONFIG_API_URL", "http://gta5rp.leetpc.com")
    CONFIG_API_SECRET: str = os.getenv("CONFIG_API_SECRET", "gta5rp_api_secret_2025")
    
    # Версия клиента
    VERSION: str = "2.0.0"
    
    # Интервалы (секунды)
    HEARTBEAT_INTERVAL: int = 30
    UPDATE_CHECK_INTERVAL: int = 300  # 5 минут
    
    # GTA5RP (загружается из account.json после get_config)
    GTA5RP_LOGIN: str = os.getenv("GTA5RP_LOGIN", "")
    GTA5RP_PASSWORD: str = os.getenv("GTA5RP_PASSWORD", "")
    
    # Epic Games
    EPIC_LOGIN: str = os.getenv("EPIC_LOGIN", "")
    EPIC_PASSWORD: str = os.getenv("EPIC_PASSWORD", "")


settings = Settings()
