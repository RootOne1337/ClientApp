"""
Time Synchronization Script - Ultra Fault-Tolerant Version
Synchronizes system time using multiple HTTP sources (no UDP/NTP required)
Works even when ISP blocks UDP or NTP ports

Sources priority:
1. HTTP Time APIs (multiple)
2. HTTPS headers from major websites
3. Fallback to any available source

Returns:
    True if time was successfully synced
    False if all attempts failed
"""

import ctypes
import sys
import time
import re
import json
import ssl
import socket
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from email.utils import parsedate_to_datetime

# Добавляем parent в path для импорта
sys.path.insert(0, str(__file__).rsplit('scripts', 1)[0])
try:
    from utils import get_logger
    logger = get_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# Moscow timezone offset (UTC+3)
MOSCOW_OFFSET = timedelta(hours=3)

# Configuration
MAX_GLOBAL_RETRIES = 2  # Reduced from 10 to 2 for speed
RETRY_DELAY = 1  # Reduced from 3 to 1 for speed
CYCLE_DELAY = 10  # Delay between full cycles
REQUEST_TIMEOUT = 15  # HTTP request timeout


class SYSTEMTIME(ctypes.Structure):
    """Windows SYSTEMTIME structure for SetLocalTime API"""
    _fields_ = [
        ("wYear", ctypes.c_ushort),
        ("wMonth", ctypes.c_ushort),
        ("wDayOfWeek", ctypes.c_ushort),
        ("wDay", ctypes.c_ushort),
        ("wHour", ctypes.c_ushort),
        ("wMinute", ctypes.c_ushort),
        ("wSecond", ctypes.c_ushort),
        ("wMilliseconds", ctypes.c_ushort),
    ]


# ============================================================================
# TIME SOURCES - Multiple fallback options
# ============================================================================

def get_time_worldtimeapi() -> Optional[datetime]:
    """WorldTimeAPI - Primary source"""
    try:
        urls = [
            "http://worldtimeapi.org/api/timezone/Europe/Moscow",
            "https://worldtimeapi.org/api/timezone/Europe/Moscow",
        ]
        for url in urls:
            try:
                req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                    data = json.loads(response.read().decode())
                    dt_str = data.get("datetime", "")
                    # Parse: "2025-06-19T14:30:00.123456+03:00"
                    match = re.match(r"(\d+)-(\d+)-(\d+)T(\d+):(\d+):(\d+)", dt_str)
                    if match:
                        y, m, d, h, mi, s = map(int, match.groups())
                        return datetime(y, m, d, h, mi, s)
            except:
                continue
    except:
        pass
    return None


def get_time_timeapi_io() -> Optional[datetime]:
    """TimeAPI.io - Alternative API"""
    try:
        url = "https://timeapi.io/api/Time/current/zone?timeZone=Europe/Moscow"
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode())
            return datetime(
                data["year"], data["month"], data["day"],
                data["hour"], data["minute"], data["seconds"]
            )
    except:
        return None


def get_time_from_http_headers(url: str) -> Optional[datetime]:
    """Extract time from HTTP Date header (works with any website)"""
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'}, method='HEAD')
        with urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            date_header = response.headers.get('Date')
            if date_header:
                # Parse RFC 2822 date and convert to Moscow time
                dt = parsedate_to_datetime(date_header)
                moscow_dt = dt.astimezone(timezone(MOSCOW_OFFSET)).replace(tzinfo=None)
                return moscow_dt
    except:
        pass
    return None


def get_time_google() -> Optional[datetime]:
    return get_time_from_http_headers("https://www.google.com")

def get_time_yandex() -> Optional[datetime]:
    return get_time_from_http_headers("https://www.yandex.ru")

def get_time_cloudflare() -> Optional[datetime]:
    return get_time_from_http_headers("https://www.cloudflare.com")

def get_time_github() -> Optional[datetime]:
    return get_time_from_http_headers("https://github.com")


# All time sources in priority order
TIME_SOURCES = [
    ("WorldTimeAPI", get_time_worldtimeapi),
    ("TimeAPI.io", get_time_timeapi_io),
    ("Yandex", get_time_yandex),
    ("Google", get_time_google),
    ("Cloudflare", get_time_cloudflare),
    ("GitHub", get_time_github),
]


# ============================================================================
# SYSTEM TIME SETTER
# ============================================================================

def set_system_time(dt: datetime) -> bool:
    """Set Windows system time using SetLocalTime API"""
    try:
        st = SYSTEMTIME()
        st.wYear = dt.year
        st.wMonth = dt.month
        st.wDay = dt.day
        st.wHour = dt.hour
        st.wMinute = dt.minute
        st.wSecond = dt.second
        st.wMilliseconds = 0
        st.wDayOfWeek = 0  # Windows calculates this

        result = ctypes.windll.kernel32.SetLocalTime(ctypes.byref(st))
        if not result:
            error = ctypes.get_last_error()
            logger.error(f"SetLocalTime failed with error code: {error}")
            return False
        return True
    except Exception as e:
        logger.error(f"Failed to set system time: {e}")
        return False


def get_current_time_from_any_source() -> Optional[Tuple[str, datetime]]:
    """Try all sources and return first successful result"""
    for name, func in TIME_SOURCES:
        try:
            logger.info(f"Trying {name}...")
            dt = func()
            if dt:
                logger.info(f"Got time from {name}: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                return (name, dt)
            else:
                logger.debug(f"{name} returned no data")
        except Exception as e:
            logger.debug(f"{name}: {e}")
        time.sleep(0.5)  # Small delay between sources
    return None


def sync_time() -> bool:
    """
    Синхронизировать системное время.
    
    Returns:
        True если время успешно синхронизировано
        False если все попытки провалились
    """
    logger.info("=" * 50)
    logger.info("🕐 Time Synchronization")
    logger.info("=" * 50)

    for cycle in range(1, MAX_GLOBAL_RETRIES + 1):
        logger.info(f"Attempt {cycle}/{MAX_GLOBAL_RETRIES}...")
        
        result = get_current_time_from_any_source()
        
        if result:
            source_name, dt = result
            logger.info(f"✅ Time from: {source_name}")
            logger.info(f"   Setting to: {dt.strftime('%d.%m.%Y %H:%M:%S')} (Moscow)")
            
            if set_system_time(dt):
                logger.info("✅ System time updated!")
                return True
            else:
                logger.error("❌ Failed to set time (need admin rights?)")
        else:
            logger.warning(f"All sources failed in attempt {cycle}")
        
        if cycle < MAX_GLOBAL_RETRIES:
            logger.info(f"Waiting {CYCLE_DELAY}s before retry...")
            time.sleep(CYCLE_DELAY)
    
    logger.error("❌ Failed to sync time after all attempts!")
    return False


# Для обратной совместимости
def main() -> int:
    """Legacy main function"""
    return 0 if sync_time() else 1


if __name__ == "__main__":
    try:
        success = sync_time()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"[CRITICAL] Unexpected error: {e}")
        sys.exit(1)
