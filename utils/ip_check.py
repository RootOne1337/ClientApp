"""
Проверка IP адреса клиента.

Логика:
- IP в BLOCKED_IPS → НЕ запускаем фарм (это домашние/офисные ПК)
- IP НЕ в списке → запускаем фарм (это VM)
- Нет интернета → пробуем восстановить подключение
"""

import httpx
import ipaddress
from typing import List, Tuple, Union
from enum import Enum


class IPStatus(Enum):
    """Статус проверки IP"""
    ALLOWED = "allowed"      # IP не в blacklist, можно работать
    BLOCKED = "blocked"      # IP в blacklist, не запускаем фарм
    NO_INTERNET = "no_internet"  # Нет подключения к интернету


# Заблокированные IP адреса и диапазоны (домашние/офисные ПК)
# На этих IP фарм НЕ запускается
BLOCKED_IPS: List[Union[str, Tuple[str, str]]] = [
    # Отдельные IP
    "212.220.204.72",
    "217.73.89.128",
    
    # Диапазоны (первый IP, последний IP)
    ("79.142.197.0", "79.142.197.255"),
    ("217.73.88.0", "217.73.91.255"),
    ("185.70.0.0", "185.70.255.255"),
]


def get_external_ip() -> str:
    """Получить внешний IP адрес"""
    try:
        response = httpx.get("https://api.ipify.org", timeout=10)
        return response.text.strip()
    except Exception:
        return ""


def ip_to_int(ip: str) -> int:
    """Конвертировать IP в число для сравнения диапазонов"""
    return int(ipaddress.ip_address(ip))


def is_ip_in_range(ip: str, start: str, end: str) -> bool:
    """Проверить входит ли IP в диапазон"""
    ip_int = ip_to_int(ip)
    return ip_to_int(start) <= ip_int <= ip_to_int(end)


def is_ip_blocked(ip: str) -> bool:
    """Проверить заблокирован ли IP (домашний/офисный)"""
    if not ip:
        return False
    
    for item in BLOCKED_IPS:
        if isinstance(item, str):
            # Отдельный IP
            if ip == item:
                return True
        elif isinstance(item, tuple) and len(item) == 2:
            # Диапазон
            if is_ip_in_range(ip, item[0], item[1]):
                return True
    
    return False


def check_ip_access() -> Tuple[IPStatus, str]:
    """
    Проверить статус IP клиента.
    
    Returns:
        (status: IPStatus, ip: str)
        
    Статусы:
        - ALLOWED: IP не в blacklist, можно запускать фарм
        - BLOCKED: IP в blacklist, фарм не запускаем
        - NO_INTERNET: Нет подключения, нужно восстановить
    """
    ip = get_external_ip()
    
    if not ip:
        return IPStatus.NO_INTERNET, ""
    
    if is_ip_blocked(ip):
        return IPStatus.BLOCKED, ip
    
    return IPStatus.ALLOWED, ip


# Тест при прямом запуске
if __name__ == "__main__":
    print("Checking IP access...")
    status, ip = check_ip_access()
    
    print(f"Your IP: {ip or 'unknown'}")
    print(f"Status: {status.value}")
    
    if status == IPStatus.ALLOWED:
        print("✅ ALLOWED - Farm will run")
    elif status == IPStatus.BLOCKED:
        print("🛑 BLOCKED - Farm will NOT run (home/office IP)")
    else:
        print("❌ NO INTERNET - Need to restore connection")
