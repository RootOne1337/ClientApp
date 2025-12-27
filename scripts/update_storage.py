"""
RageMP Storage.json Updater

Updates C:\Games\GTA5RP\RageMP\clientdata\cef\clientdata\storage.json
with the correct server from account config.

Reads server_hostname from data/account.json and sets it as the favorite server.

Returns:
    True if storage.json was successfully updated
    False if failed
"""

import os
import sys
import json
from pathlib import Path

# Добавляем parent в path для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from config import ACCOUNT_FILE
    from utils import get_logger
    logger = get_logger()
except ImportError:
    print("Error: Run from client directory")
    sys.exit(1)

# Путь к storage.json (RageMP)
STORAGE_JSON_PATH = Path(r"C:\Games\GTA5RP\RageMP\clientdata\cef\clientdata\storage.json")


def load_account_config() -> dict:
    """Загрузить конфиг аккаунта"""
    try:
        if ACCOUNT_FILE.exists():
            with open(ACCOUNT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load account config: {e}")
    return {}


def create_storage_json(server_hostname: str) -> dict:
    """
    Создать структуру storage.json
    
    Args:
        server_hostname: Хост сервера (например v3-downtown.gta5rp.com)
    """
    if not server_hostname:
        # Ошибка — нет сервера
        return {
            "tab": "favorites",
            "favorites": [
                {
                    "ip": "",
                    "name": "ERROR: Server not configured!",
                    "port": 22005
                }
            ],
            "history": []
        }
    
    return {
        "tab": "favorites",
        "favorites": [
            {
                "ip": server_hostname,
                "name": "V3 SERVER",
                "port": 22005
            }
        ],
        "history": [
            {
                "ip": server_hostname,
                "name": f"{server_hostname}:22005",
                "port": "22005"
            }
        ]
    }


def update_storage() -> bool:
    """
    Обновить storage.json с сервером из account.json
    
    Returns:
        True если успешно
        False если ошибка
    """
    logger.info("=" * 50)
    logger.info("🎮 Updating RageMP Storage")
    logger.info("=" * 50)
    
    # 1. Загружаем конфиг аккаунта
    account = load_account_config()
    if not account:
        logger.error("❌ No account config found")
        logger.error(f"   Expected: {ACCOUNT_FILE}")
        return False
    
    # 2. Получаем server_hostname
    server_hostname = account.get("server_hostname", "")
    server_nickname = account.get("server", "")
    
    if not server_hostname:
        logger.error("❌ No server_hostname in account config")
        logger.error("   Run get_config.py first!")
        return False
    
    logger.info(f"Server: {server_nickname}")
    logger.info(f"Hostname: {server_hostname}")
    
    # 3. Создаём структуру storage.json
    storage_data = create_storage_json(server_hostname)
    
    # 4. Проверяем что папка существует
    storage_dir = STORAGE_JSON_PATH.parent
    if not storage_dir.exists():
        logger.warning(f"⚠️ Creating directory: {storage_dir}")
        try:
            storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"❌ Failed to create directory: {e}")
            return False
    
    # 5. Записываем storage.json
    try:
        with open(STORAGE_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(storage_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Storage updated: {STORAGE_JSON_PATH}")
        logger.info(f"   Favorite server: {server_hostname}:22005")
        return True
        
    except PermissionError:
        logger.error(f"❌ Permission denied: {STORAGE_JSON_PATH}")
        logger.error("   Try running as Administrator")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to write storage.json: {e}")
        return False


if __name__ == "__main__":
    success = update_storage()
    sys.exit(0 if success else 1)
