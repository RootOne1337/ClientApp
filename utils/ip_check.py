"""
Проверка IP адреса клиента.
Бот работает только с разрешённых IP адресов.
"""

import httpx
import ipaddress
from typing import List, Tuple, Union


# Разрешённые IP адреса и диапазоны
ALLOWED_IPS: List[Union[str, Tuple[str, str]]] = [
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
    except Exception as e:
        print(f"❌ Failed to get external IP: {e}")
        return ""


def ip_to_int(ip: str) -> int:
    """Конвертировать IP в число для сравнения диапазонов"""
    return int(ipaddress.ip_address(ip))


def is_ip_in_range(ip: str, start: str, end: str) -> bool:
    """Проверить входит ли IP в диапазон"""
    ip_int = ip_to_int(ip)
    return ip_to_int(start) <= ip_int <= ip_to_int(end)


def is_ip_allowed(ip: str) -> bool:
    """Проверить разрешён ли IP"""
    if not ip:
        return False
    
    for item in ALLOWED_IPS:
        if isinstance(item, str):
            # Отдельный IP
            if ip == item:
                return True
        elif isinstance(item, tuple) and len(item) == 2:
            # Диапазон
            if is_ip_in_range(ip, item[0], item[1]):
                return True
    
    return False


def check_ip_access() -> Tuple[bool, str]:
    """
    Проверить имеет ли текущий клиент доступ.
    
    Returns:
        (allowed: bool, ip: str)
    """
    ip = get_external_ip()
    
    if not ip:
        return False, "unknown"
    
    allowed = is_ip_allowed(ip)
    return allowed, ip


# Тест при прямом запуске
if __name__ == "__main__":
    print("Checking IP access...")
    allowed, ip = check_ip_access()
    print(f"Your IP: {ip}")
    print(f"Access: {'✅ ALLOWED' if allowed else '❌ DENIED'}")
