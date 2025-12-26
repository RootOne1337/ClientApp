"""
Account Config Fetcher

Gets account configuration from GTA5RP API based on external IP.
Saves to data/account.json and data/credentials.json

Returns:
    True if config was successfully fetched and saved
    False if failed
"""

import os
import json
import sys
from pathlib import Path

# Добавляем parent в path для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from config import settings, ACCOUNT_FILE, CREDENTIALS_FILE, DATA_DIR
    from utils import get_logger
    logger = get_logger()
except ImportError:
    print("Error: Run from client directory")
    sys.exit(1)

try:
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "urllib3"])
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_external_ip() -> str:
    """Получить внешний IP адрес"""
    try:
        response = requests.get("https://api.ipify.org?format=json", timeout=5)
        response.raise_for_status()
        return response.json().get("ip", "")
    except:
        try:
            response = requests.get("https://ifconfig.me", timeout=5)
            return response.text.strip()
        except:
            return ""


def get_config_from_api(ip: str) -> dict:
    """Получить конфигурацию с API сервера"""
    try:
        # Получаем токен
        token_url = f"{settings.CONFIG_API_URL}/api/v1/auth/token"
        token_data = {
            "ip": ip,
            "secret": settings.CONFIG_API_SECRET
        }
        headers = {"X-Forwarded-For": ip}
        
        token_response = requests.post(
            token_url,
            json=token_data,
            headers=headers,
            timeout=10,
            verify=False
        )
        
        if token_response.status_code != 200:
            logger.error(f"Token error: {token_response.status_code}")
            return {}
        
        access_token = token_response.json().get("access_token")
        logger.info("✅ Token obtained")
        
        # Получаем конфиг
        config_url = f"{settings.CONFIG_API_URL}/api/v1/config"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Forwarded-For": ip
        }
        
        config_response = requests.get(
            config_url,
            headers=headers,
            timeout=10,
            verify=False
        )
        
        if config_response.status_code != 200:
            logger.error(f"Config error: {config_response.status_code}")
            return {}
        
        return config_response.json()
        
    except Exception as e:
        logger.error(f"API request failed: {e}")
        return {}


def save_account_config(config: dict) -> bool:
    """Сохранить конфигурацию аккаунта в JSON"""
    try:
        # Извлекаем нужные поля
        account_data = {
            "active_character": config.get("active_character", ""),
            "email": config.get("email", ""),
            "password": config.get("password", ""),
            "imap": config.get("imap", ""),
            "social_login": config.get("social_login", ""),
            "social_password": config.get("social_password", ""),
            "pcname": config.get("pcname", ""),
            "login": config.get("login", ""),
            "epic_login": config.get("epic_login", ""),
            "epic_password": config.get("epic_password", ""),
        }
        
        # Сохраняем
        DATA_DIR.mkdir(exist_ok=True)
        with open(ACCOUNT_FILE, "w", encoding="utf-8") as f:
            json.dump(account_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Account config saved to {ACCOUNT_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save account config: {e}")
        return False


def save_credentials(config: dict) -> bool:
    """Сохранить Google credentials в JSON"""
    try:
        google_credentials = config.get("google_credentials")
        if not google_credentials:
            logger.info("No Google credentials in config (skipping)")
            return True
        
        DATA_DIR.mkdir(exist_ok=True)
        with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
            json.dump(google_credentials, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Google credentials saved to {CREDENTIALS_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save credentials: {e}")
        return False


def load_account_config() -> dict:
    """Загрузить сохранённый конфиг аккаунта"""
    try:
        if ACCOUNT_FILE.exists():
            with open(ACCOUNT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load account config: {e}")
    return {}


def fetch_config() -> bool:
    """
    Получить и сохранить конфигурацию аккаунта.
    
    Returns:
        True если успешно
        False если ошибка
    """
    logger.info("=" * 50)
    logger.info("📦 Fetching Account Config")
    logger.info("=" * 50)
    
    # Получаем IP
    external_ip = get_external_ip()
    if not external_ip:
        logger.error("❌ Failed to get external IP")
        return False
    
    logger.info(f"IP: {external_ip}")
    
    # Получаем конфиг
    config = get_config_from_api(external_ip)
    if not config:
        logger.error("❌ Failed to get config from API")
        return False
    
    # Сохраняем
    if not save_account_config(config):
        return False
    
    save_credentials(config)  # Опционально
    
    logger.info("✅ Config fetched successfully!")
    return True


if __name__ == "__main__":
    success = fetch_config()
    sys.exit(0 if success else 1)
