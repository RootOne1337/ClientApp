"""
Time Synchronization Script - Ultra Fault-Tolerant Version
Synchronizes system time using multiple HTTP sources (no UDP/NTP required)
Works even when ISP blocks UDP or NTP ports

Sources priority:
1. HTTP Time APIs (multiple)
2. HTTPS headers from major websites
3. Fallback to any available source
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


def get_time_worldclockapi() -> Optional[datetime]:
    """WorldClockAPI - Another alternative"""
    try:
        url = "http://worldclockapi.com/api/json/utc/now"
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode())
            dt_str = data.get("currentDateTime", "")
            # Parse UTC and convert to Moscow
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            moscow_dt = dt.replace(tzinfo=None) + MOSCOW_OFFSET
            return moscow_dt
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
    """Get time from Google's HTTP header"""
    return get_time_from_http_headers("https://www.google.com")


def get_time_cloudflare() -> Optional[datetime]:
    """Get time from Cloudflare's HTTP header"""
    return get_time_from_http_headers("https://www.cloudflare.com")


def get_time_microsoft() -> Optional[datetime]:
    """Get time from Microsoft's HTTP header"""
    return get_time_from_http_headers("https://www.microsoft.com")


def get_time_amazon() -> Optional[datetime]:
    """Get time from Amazon's HTTP header"""
    return get_time_from_http_headers("https://www.amazon.com")


def get_time_yandex() -> Optional[datetime]:
    """Get time from Yandex's HTTP header (Russian server, good for Moscow)"""
    return get_time_from_http_headers("https://www.yandex.ru")


def get_time_mail_ru() -> Optional[datetime]:
    """Get time from Mail.ru's HTTP header"""
    return get_time_from_http_headers("https://www.mail.ru")


def get_time_vk() -> Optional[datetime]:
    """Get time from VK's HTTP header"""
    return get_time_from_http_headers("https://www.vk.com")


def get_time_github() -> Optional[datetime]:
    """Get time from GitHub's HTTP header"""
    return get_time_from_http_headers("https://github.com")


def get_time_apple() -> Optional[datetime]:
    """Get time from Apple's HTTP header"""
    return get_time_from_http_headers("https://www.apple.com")


def get_time_httpbin() -> Optional[datetime]:
    """HTTPBin - Returns current time in response"""
    try:
        url = "http://httpbin.org/headers"
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            date_header = response.headers.get('Date')
            if date_header:
                dt = parsedate_to_datetime(date_header)
                moscow_dt = dt.astimezone(timezone(MOSCOW_OFFSET)).replace(tzinfo=None)
                return moscow_dt
    except:
        pass
    return None


# All time sources in priority order
TIME_SOURCES = [
    ("WorldTimeAPI", get_time_worldtimeapi),
    ("TimeAPI.io", get_time_timeapi_io),
    ("Yandex", get_time_yandex),
    ("Mail.ru", get_time_mail_ru),
    ("VK", get_time_vk),
    ("Google", get_time_google),
    ("Cloudflare", get_time_cloudflare),
    ("Microsoft", get_time_microsoft),
    ("GitHub", get_time_github),
    ("Amazon", get_time_amazon),
    ("Apple", get_time_apple),
    ("WorldClockAPI", get_time_worldclockapi),
    ("HTTPBin", get_time_httpbin),
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
            print(f"[ERROR] SetLocalTime failed with error code: {error}", flush=True)
            return False
        return True
    except Exception as e:
        print(f"[ERROR] Failed to set system time: {e}", flush=True)
        return False


def get_current_time_from_any_source() -> Optional[Tuple[str, datetime]]:
    """Try all sources and return first successful result"""
    for name, func in TIME_SOURCES:
        try:
            print(f"[INFO] Trying {name}...", flush=True)
            dt = func()
            if dt:
                print(f"[OK] Got time from {name}: {dt.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
                return (name, dt)
            else:
                print(f"[FAIL] {name} returned no data", flush=True)
        except Exception as e:
            print(f"[FAIL] {name}: {e}", flush=True)
        time.sleep(0.5)  # Small delay between sources
    return None


def main():
    """Main function - keeps trying until time is synchronized"""
    print("=" * 60, flush=True)
    print("TIME SYNCHRONIZATION - Ultra Fault-Tolerant", flush=True)
    print("=" * 60, flush=True)
    print(f"Available sources: {len(TIME_SOURCES)}", flush=True)
    print("", flush=True)

    for cycle in range(1, MAX_GLOBAL_RETRIES + 1):
        print(f"[CYCLE {cycle}/{MAX_GLOBAL_RETRIES}] Attempting time sync...", flush=True)
        
        result = get_current_time_from_any_source()
        
        if result:
            source_name, dt = result
            print("", flush=True)
            print(f"[SUCCESS] Time obtained from: {source_name}", flush=True)
            print(f"[INFO] Setting system time to: {dt.strftime('%d.%m.%Y %H:%M:%S')} (Moscow)", flush=True)
            
            if set_system_time(dt):
                print("[OK] System time successfully updated!", flush=True)
                print("=" * 60, flush=True)
                return 0
            else:
                print("[ERROR] Failed to set system time (need admin rights?)", flush=True)
        else:
            print(f"[WARN] All sources failed in cycle {cycle}", flush=True)
        
        if cycle < MAX_GLOBAL_RETRIES:
            print(f"[INFO] Waiting {CYCLE_DELAY}s before next cycle...", flush=True)
            print("", flush=True)
            time.sleep(CYCLE_DELAY)
    
    print("[CRITICAL] Failed to sync time after all attempts!", flush=True)
    print("=" * 60, flush=True)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user", flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"[CRITICAL] Unexpected error: {e}", flush=True)
        sys.exit(1)
