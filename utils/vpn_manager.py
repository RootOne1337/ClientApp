"""
VPN Manager — управление VPN подключениями.

Поддерживает:
- AmneziaVPN
- WireGuard

Функции:
- Проверка запущен ли VPN процесс
- Проверка установлен ли VPN
- Запуск VPN приложения
"""

import subprocess
import os
from pathlib import Path
from typing import Optional, List, Tuple
from utils import get_logger

logger = get_logger()


# VPN конфигурация
VPN_APPS = {
    "amnezia": {
        "process_name": "AmneziaVPN.exe",
        "install_path": r"C:\Program Files\AmneziaVPN\AmneziaVPN.exe",
    },
    "wireguard": {
        "process_name": "wireguard.exe",
        "install_path": r"C:\Program Files\WireGuard\wireguard.exe",
    }
}


def is_process_running(process_name: str) -> bool:
    """Проверить запущен ли процесс"""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return process_name.lower() in result.stdout.lower()
    except Exception as e:
        logger.error(f"Error checking process {process_name}: {e}")
        return False


def is_vpn_installed(vpn_name: str) -> bool:
    """Проверить установлен ли VPN"""
    if vpn_name not in VPN_APPS:
        return False
    
    install_path = VPN_APPS[vpn_name]["install_path"]
    return Path(install_path).exists()


def is_vpn_running(vpn_name: str) -> bool:
    """Проверить запущен ли VPN процесс"""
    if vpn_name not in VPN_APPS:
        return False
    
    process_name = VPN_APPS[vpn_name]["process_name"]
    return is_process_running(process_name)


def start_vpn(vpn_name: str) -> bool:
    """Запустить VPN приложение"""
    if vpn_name not in VPN_APPS:
        logger.warning(f"Unknown VPN: {vpn_name}")
        return False
    
    install_path = VPN_APPS[vpn_name]["install_path"]
    
    if not Path(install_path).exists():
        logger.warning(f"{vpn_name} not installed at {install_path}")
        return False
    
    try:
        logger.info(f"🚀 Starting {vpn_name}...")
        subprocess.Popen(
            [install_path],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        )
        return True
    except Exception as e:
        logger.error(f"Failed to start {vpn_name}: {e}")
        return False


def get_vpn_status() -> dict:
    """Получить статус всех VPN"""
    status = {}
    for vpn_name, config in VPN_APPS.items():
        status[vpn_name] = {
            "installed": is_vpn_installed(vpn_name),
            "running": is_vpn_running(vpn_name),
        }
    return status


def try_start_any_vpn() -> Tuple[bool, List[str]]:
    """
    Попытаться запустить любой доступный VPN.
    
    Returns:
        (success: bool, started: list of vpn names that were started)
    """
    started = []
    
    for vpn_name in VPN_APPS:
        # Если уже запущен — пропускаем
        if is_vpn_running(vpn_name):
            logger.info(f"✅ {vpn_name} already running")
            continue
        
        # Если установлен — запускаем
        if is_vpn_installed(vpn_name):
            if start_vpn(vpn_name):
                started.append(vpn_name)
    
    return len(started) > 0, started


def any_vpn_running() -> bool:
    """Проверить запущен ли хотя бы один VPN"""
    for vpn_name in VPN_APPS:
        if is_vpn_running(vpn_name):
            return True
    return False


def any_vpn_installed() -> bool:
    """Проверить установлен ли хотя бы один VPN"""
    for vpn_name in VPN_APPS:
        if is_vpn_installed(vpn_name):
            return True
    return False


# Тест
if __name__ == "__main__":
    print("VPN Status:")
    status = get_vpn_status()
    for vpn, info in status.items():
        print(f"  {vpn}: installed={info['installed']}, running={info['running']}")
    
    print("\nAny VPN running:", any_vpn_running())
    print("Any VPN installed:", any_vpn_installed())
