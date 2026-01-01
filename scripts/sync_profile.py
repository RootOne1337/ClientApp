#!/usr/bin/env python3
"""
Sync Profile Script
Fetches GTA5RP profile data from API and sends to our server.
Runs on CLIENT (same IP as game) to avoid bans.

OPTIMIZATIONS:
- Uses cached token (valid ~30 days with remember=1)
- Queries only specified server (not all 23)
- Auto re-login on 401 errors
"""

import json
import sys
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

from game.gta5rp_session import get_session, SERVER_NAMES

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# GTA5RP API
GTA5RP_API = "https://gta5rp.com/api/V2"

# Server names mapping (now imported from gta5rp_session)
# Kept here for backward compatibility if needed


# Removed: gta5rp_login() - now handled by GTA5RPSession


# Removed: get_user_info() - now handled by GTA5RPSession


# Removed: get_all_characters() - now using get_characters_for_server() from session


def get_online_character(characters: List[Dict]) -> Optional[Dict]:
    """Find the currently online character"""
    for char in characters:
        if char.get("is_online"):
            return char
    return None


def sync_profile(login: str, password: str, server_api_url: str, machine_id: str, server_name: str = None) -> bool:
    """
    Main sync function (OPTIMIZED):
    1. Login to GTA5RP (uses cached token if available)
    2. Get user info + characters from SPECIFIC server
    3. Send to our server
    
    Args:
        server_name: Server to query (e.g. "09.Eclipse"). If None, queries all servers (not recommended).
    """
    logger.info(f"Starting profile sync for machine {machine_id}")
    
    # Get global session
    session = get_session()
    
    # Step 1: Login if needed (uses cached token if valid)
    if not session.login_if_needed(login, password):
        logger.error("Failed to authenticate")
        return False
    
    # Step 2: Get user info
    user_info = session.get_user_info()
    if not user_info:
        # Token might be expired, try re-login
        logger.info("Retrying with forced re-login...")
        if session.login_if_needed(login, password, force=True):
            user_info = session.get_user_info()
        
        if not user_info:
            logger.error("Failed to get user info")
            return False
    
    logger.info(f"User: {user_info.get('login')}, Balance: {user_info.get('balance')}")
    
    # Step 3: Get characters ONLY from specified server (optimization!)
    characters = []
    if server_name:
        logger.info(f"Querying only server: {server_name}")
        characters = session.get_characters_for_server(server_name)
    else:
        logger.warning("No server specified, skipping character fetch")
        # Could fallback to querying all servers here if needed
    
    logger.info(f"Found {len(characters)} characters on {server_name or 'all servers'}")
    
    # Step 4: Find online character
    online_char = get_online_character(characters)
    if online_char:
        logger.info(f"Online: {online_char.get('name')} on {online_char.get('server_name')}")
    
    # Step 5: Build sync payload
    payload = {
        "machine_id": machine_id,
        "timestamp": int(time.time()),
        "user": {
            "login": user_info.get("login"),
            "email": user_info.get("email"),
            "balance": user_info.get("balance", 0),
            "total_donate": user_info.get("total_donate", 0),
            "last_server": user_info.get("last_server"),
        },
        "characters": [],
        "online_character": None
    }
    
    # Add character data (cleaned up)
    for char in characters:
        char_data = {
            "char_id": char.get("id"),
            "name": char.get("name"),
            "server_id": char.get("server_id"),
            "server_name": char.get("server_name"),
            "is_online": bool(char.get("is_online")),
            "lvl": char.get("lvl", 0),
            "exp": char.get("exp", 0),
            "max_exp": char.get("max_exp", 0),
            "cash": char.get("cash", 0),
            "bank": char.get("bank", 0),
            "total_money": char.get("cash", 0) + char.get("bank", 0),
            "has_house": bool(char.get("house")),
            "has_apartment": bool(char.get("apartment")),
            "has_business": bool(char.get("business")),
            "vehicles_count": len(char.get("vehicles", []) or []),
            "vehicles": char.get("vehicles", []),
            "hours_played": char.get("hours_played", 0),
            "vip_level": char.get("vip_level", 0),
            "vip_name": char.get("vip_name", ""),
            "vip_expire_at": char.get("vip_expire_at", 0),
            "fraction": char.get("fraction", "-"),
        }
        payload["characters"].append(char_data)
        
        if char.get("is_online"):
            payload["online_character"] = char_data
    
    # Step 6: Send to our server
    try:
        url = f"{server_api_url}/api/profiles/sync"
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"✓ Profile synced successfully")
            return True
        else:
            logger.error(f"Server error: {response.status_code} - {response.text}")
            return False
            
    except requests.RequestException as e:
        logger.error(f"Failed to send to server: {e}")
        return False


def main():
    """Command line interface"""
    if len(sys.argv) < 5:
        print("Usage: sync_profile.py <login> <password> <server_api_url> <machine_id>")
        print("Example: sync_profile.py example@mail.ru password123 http://server.com 5")
        sys.exit(1)
    
    login = sys.argv[1]
    password = sys.argv[2]
    server_api_url = sys.argv[3]
    machine_id = sys.argv[4]
    
    success = sync_profile(login, password, server_api_url, machine_id)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
