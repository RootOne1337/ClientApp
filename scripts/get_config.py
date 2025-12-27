"""
Account Config Fetcher

Gets account configuration and credentials from API.
Uses separate endpoints for flexibility:
- /api/v1/config-only - account data (logins, passwords)
- /api/v1/credentials - Google Sheets credentials (can be disabled later)

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


def get_jwt_token(ip: str) -> str:
    """Получить JWT токен для API"""
    try:
        token_url = f"{settings.CONFIG_API_URL}/api/v1/auth/token"
        token_data = {
            "ip": ip,
            "secret": settings.CONFIG_API_SECRET
        }
        headers = {"X-Forwarded-For": ip}
        
        response = requests.post(
            token_url,
            json=token_data,
            headers=headers,
            timeout=10,
            verify=False
        )
        
        if response.status_code != 200:
            logger.error(f"Token error: {response.status_code}")
            return ""
        
        return response.json().get("access_token", "")
        
    except Exception as e:
        logger.error(f"Token request failed: {e}")
        return ""


def get_account_config(token: str, ip: str) -> dict:
    """Получить конфигурацию аккаунта (БЕЗ credentials)"""
    try:
        config_url = f"{settings.CONFIG_API_URL}/api/v1/config-only"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Forwarded-For": ip
        }
        
        response = requests.get(
            config_url,
            headers=headers,
            timeout=10,
            verify=False
        )
        
        if response.status_code != 200:
            logger.error(f"Config error: {response.status_code}")
            return {}
        
        return response.json()
        
    except Exception as e:
        logger.error(f"Config request failed: {e}")
        return {}


def get_google_credentials(token: str, ip: str) -> dict:
    """Получить Google credentials (отдельный запрос)"""
    try:
        creds_url = f"{settings.CONFIG_API_URL}/api/v1/credentials"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Forwarded-For": ip
        }
        
        response = requests.get(
            creds_url,
            headers=headers,
            timeout=10,
            verify=False
        )
        
        if response.status_code != 200:
            # Не критично — credentials могут быть не нужны
            logger.warning(f"Credentials not available: {response.status_code}")
            return {}
        
        return response.json().get("google_credentials", {})
        
    except Exception as e:
        logger.warning(f"Credentials request failed: {e}")
        return {}


def save_account_config(config: dict) -> bool:
    """Сохранить конфигурацию аккаунта в JSON"""
    try:
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
        
        DATA_DIR.mkdir(exist_ok=True)
        with open(ACCOUNT_FILE, "w", encoding="utf-8") as f:
            json.dump(account_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Account config saved to {ACCOUNT_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save account config: {e}")
        return False


def save_credentials(credentials: dict) -> bool:
    """Сохранить Google credentials в JSON"""
    try:
        if not credentials:
            logger.info("No Google credentials (skipping)")
            return True
        
        DATA_DIR.mkdir(exist_ok=True)
        with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
            json.dump(credentials, f, indent=2, ensure_ascii=False)
        
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
    
    Делает 3 запроса:
    1. /auth/token - получить JWT
    2. /config-only - получить данные аккаунта
    3. /credentials - получить Google credentials (опционально)
    
    Returns:
        True если успешно
        False если ошибка
    """
    logger.info("=" * 50)
    logger.info("📦 Fetching Account Config")
    logger.info("=" * 50)
    
    # 1. Получаем IP
    external_ip = get_external_ip()
    if not external_ip:
        logger.error("❌ Failed to get external IP")
        return False
    
    logger.info(f"IP: {external_ip}")
    
    # 2. Получаем JWT токен
    logger.info("📍 Step 1: Getting JWT token...")
    token = get_jwt_token(external_ip)
    if not token:
        logger.error("❌ Failed to get token")
        return False
    logger.info("✅ Token obtained")
    
    # 3. Получаем конфиг аккаунта
    logger.info("📍 Step 2: Getting account config...")
    config = get_account_config(token, external_ip)
    if not config:
        logger.error("❌ Failed to get config")
        return False
    
    if not save_account_config(config):
        return False
    
    # 4. Получаем credentials (опционально)
    logger.info("📍 Step 3: Getting credentials...")
    credentials = get_google_credentials(token, external_ip)
    save_credentials(credentials)  # Не критично если не получится
    
    logger.info("")
    logger.info("=" * 50)
    logger.info("✅ Config fetched successfully!")
    logger.info("=" * 50)
    return True


if __name__ == "__main__":
    success = fetch_config()
    sys.exit(0 if success else 1)
