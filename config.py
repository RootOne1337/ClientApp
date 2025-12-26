import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

# Пути
APP_DIR = Path(__file__).parent.absolute()
DATA_DIR = APP_DIR / "data"
LOGS_DIR = APP_DIR / "logs"
SCREENSHOTS_DIR = APP_DIR / "screenshots"

# Создаём директории
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
SCREENSHOTS_DIR.mkdir(exist_ok=True)


class Settings:
    # API сервера
    API_URL: str = os.getenv("API_URL", "http://gta5rp.leetpc.com/api")
    
    # Версия клиента
    VERSION: str = "2.0.0"
    
    # Интервалы (секунды)
    HEARTBEAT_INTERVAL: int = 30
    UPDATE_CHECK_INTERVAL: int = 300  # 5 минут
    
    # GTA5RP
    GTA5RP_LOGIN: str = os.getenv("GTA5RP_LOGIN", "")
    GTA5RP_PASSWORD: str = os.getenv("GTA5RP_PASSWORD", "")
    
    # Epic Games
    EPIC_LOGIN: str = os.getenv("EPIC_LOGIN", "")
    EPIC_PASSWORD: str = os.getenv("EPIC_PASSWORD", "")


settings = Settings()
