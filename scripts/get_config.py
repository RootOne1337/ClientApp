#!/usr/bin/env python3
"""
Standalone клиент для получения конфигурации с GTA5RP API
Интегрирован в GTA5rpVirt

Процесс:
1. Получает внешний IP адрес
2. Отправляет IP на API сервер
3. Получает конфигурацию аккаунта
4. Сохраняет в config.txt и credentials.json в корневую папку бота
"""
import os
import json
import sys
import subprocess
from pathlib import Path

# Ensure stdout/stderr always allow Unicode output on legacy consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import requests
    import urllib3
except ImportError:
    print("Библиотека requests не найдена. Устанавливаю...", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "urllib3"])
    import requests
    import urllib3

# ============================================================================
# ⚙️  КОНФИГУРАЦИЯ
# ============================================================================
API_URL = "http://gta5rp-api.leetpc.com"
API_SECRET = "gta5rp_api_secret_2025"
# ============================================================================

# Файлы будут сохранены в родительской папке (корень бота / Release)
SCRIPT_DIR = Path(__file__).parent
BOT_ROOT = SCRIPT_DIR.parent
CONFIG_FILE = BOT_ROOT / "config.txt"
CREDENTIALS_FILE = BOT_ROOT / "credentials.json"
UPDATE_GTA_SETTINGS_SCRIPT = SCRIPT_DIR / "update_gta_settings.py"

def get_external_ip():
    """Получает внешний IP адрес из интернета"""
    try:
        print("📍 Получаем внешний IP адрес...")
        response = requests.get("https://api.ipify.org?format=json", timeout=5)
        response.raise_for_status()
        ip = response.json().get("ip")
        print(f"✓ Внешний IP получен: {ip}")
        return ip
    except Exception as e:
        print(f"✗ Ошибка при получении IP: {e}")
        try:
            print("  Пробуем альтернативный способ...")
            response = requests.get("https://ifconfig.me", timeout=5)
            ip = response.text.strip()
            print(f"✓ IP получен (альтернативный метод): {ip}")
            return ip
        except Exception as e2:
            print(f"✗ Оба метода не сработали: {e2}")
            return None

def get_config_from_api(ip: str, secret: str) -> dict or None:
    """Получает конфигурацию с API сервера"""
    try:
        print(f"\n🔐 Получаем токен для IP {ip}...")
        
        token_url = f"{API_URL}/api/v1/auth/token"
        token_data = {
            "ip": ip,
            "secret": secret
        }
        
        headers = {
            "X-Forwarded-For": ip
        }
        
        token_response = requests.post(
            token_url,
            json=token_data,
            headers=headers,
            timeout=10,
            verify=False
        )
        
        if token_response.status_code != 200:
            print(f"✗ Ошибка получения токена: {token_response.status_code}")
            print(f"  Ответ: {token_response.text}")
            return None
        
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        print(f"✓ Токен получен успешно")
        
        print(f"\n📦 Получаем конфигурацию...")
        config_url = f"{API_URL}/api/v1/config"
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
            print(f"✗ Ошибка получения конфигурации: {config_response.status_code}")
            return None
        
        return config_response.json()
        
    except Exception as e:
        print(f"✗ Ошибка при запросе к API: {e}")
        return None

def save_config_to_file(config: dict, filepath: Path):
    """Сохраняет конфигурацию в текстовый файл в формате key=value;"""
    try:
        print(f"\n💾 Сохраняем конфигурацию в {filepath}...")
        
        config_lines = []
        mapping = {
            "active_character": "Active Character",
            "email": "Email",
            "password": "Password",
            "imap": "IMAP",
            "social_login": "SocialLogin",
            "social_password": "SocialPassword",
            "pcname": "PCNAME",
            "login": "Login",
            "epic_login": "EpicLogin",
            "epic_password": "EpicPassword",
        }
        
        for key, label in mapping.items():
            value = config.get(key, "")
            if value is None:
                value = ""
            config_lines.append(f"{label}={value};")
        
        config_text = "\n".join(config_lines)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(config_text)
        
        print(f"✓ Конфигурация сохранена")
        return True
    except Exception as e:
        print(f"✗ Ошибка при сохранении конфигурации: {e}")
        return False

def save_credentials_to_file(config: dict, filepath: Path):
    """Сохраняет Google Sheets credentials в JSON файл"""
    try:
        google_credentials = config.get("google_credentials")
        if not google_credentials:
            print(f"\n⚠️  Google credentials не получены от API (пропускаем)")
            return True
        
        print(f"\n💾 Сохраняем Google credentials в {filepath}...")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(google_credentials, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Google credentials сохранены")
        return True
    except Exception as e:
        print(f"✗ Ошибка при сохранении credentials: {e}")
        return False

def main():
    print("=" * 70)
    print("🚀 GTA5RP Config Client (Integrated)")
    print("=" * 70)
    
    external_ip = get_external_ip()
    if not external_ip:
        return False
    
    config = get_config_from_api(external_ip, API_SECRET)
    if not config:
        return False
    
    if not save_config_to_file(config, CONFIG_FILE):
        return False
    
    save_credentials_to_file(config, CREDENTIALS_FILE)

    # Optional post-sync step: update GTA V settings.xml (GPU name etc).
    try:
        if UPDATE_GTA_SETTINGS_SCRIPT.exists():
            print("\n🛠️  Running update_gta_settings.py...", flush=True)
            completed = subprocess.run(
                [sys.executable, str(UPDATE_GTA_SETTINGS_SCRIPT), "--no-kill"],
                cwd=str(BOT_ROOT),
                capture_output=True,
                text=True,
                timeout=60,
            )
            if completed.stdout:
                print(completed.stdout.strip(), flush=True)
            if completed.returncode != 0:
                err = (completed.stderr or "").strip()
                if err:
                    print(err, flush=True)
                print("⚠️  update_gta_settings.py failed (continuing).", flush=True)
        else:
            print("\nℹ️  update_gta_settings.py not found (skipping).", flush=True)
    except Exception as e:
        print(f"\n⚠️  update_gta_settings step failed (continuing): {e}", flush=True)
    
    print("\n" + "=" * 70)
    print("✅ УСПЕХ! Конфигурация обновлена.")
    print("=" * 70)
    return True

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Ошибка: {e}")
        sys.exit(1)
