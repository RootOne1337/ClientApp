#!/usr/bin/env python3
"""
Sync Profile Script
Fetches GTA5RP profile data from API and sends to our server.
Runs on CLIENT (same IP as game) to avoid bans.
"""

import json
import sys
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# GTA5RP API
GTA5RP_API = "https://gta5rp.com/api/V2"

# Server names mapping
SERVER_NAMES = {
    1: "01.Downtown", 2: "02.Strawberry", 3: "03.Vinewood", 4: "04.Blackberry",
    5: "05.Insquad", 6: "06.Sunrise", 7: "07.Rainbow", 8: "08.Richman",
    9: "09.Eclipse", 10: "10.LaMesa", 11: "11.Burton", 12: "12.Rockford",
    13: "13.Alta", 14: "14.DelPerro", 15: "15.Davis", 16: "16.Harmony",
    17: "17.Redwood", 18: "18.Hawick", 19: "19.Grapeseed", 20: "20.Murrieta",
    21: "21.Vespucci", 22: "22.Milton", 23: "23.LaPuerta"
}


def gta5rp_login(login: str, password: str) -> Optional[str]:
    """Login to GTA5RP and return token"""
    try:
        url = f"{GTA5RP_API}/users/auth/login"
        payload = {"login": login, "password": password, "remember": "0"}
        
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        if "token" in data:
            logger.info(f"GTA5RP login successful (user_id: {data.get('user_id')})")
            return data["token"]
        else:
            logger.error(f"GTA5RP login failed: {data}")
            return None
            
    except requests.RequestException as e:
        logger.error(f"GTA5RP login error: {e}")
        return None


def get_user_info(token: str) -> Optional[Dict[str, Any]]:
    """Get user account info (balance, email, etc)"""
    try:
        url = f"{GTA5RP_API}/users/"
        headers = {"x-access-token": token}
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        return response.json()
        
    except requests.RequestException as e:
        logger.error(f"Get user info error: {e}")
        return None


def get_all_characters(token: str) -> List[Dict[str, Any]]:
    """Get all characters from all servers"""
    characters = []
    headers = {"x-access-token": token}
    
    for server_id in range(1, 23):
        try:
            url = f"{GTA5RP_API}/users/chars/{server_id}"
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                continue
            
            data = response.json()
            if isinstance(data, list):
                for char in data:
                    char["server_id"] = server_id
                    char["server_name"] = SERVER_NAMES.get(server_id, f"Server{server_id}")
                    characters.append(char)
                    
        except Exception as e:
            logger.warning(f"Error fetching server {server_id}: {e}")
            continue
    
    return characters


def get_online_character(characters: List[Dict]) -> Optional[Dict]:
    """Find the currently online character"""
    for char in characters:
        if char.get("is_online"):
            return char
    return None


def sync_profile(login: str, password: str, server_api_url: str, machine_id: str) -> bool:
    """
    Main sync function:
    1. Login to GTA5RP
    2. Get user info + characters
    3. Send to our server
    """
    logger.info(f"Starting profile sync for machine {machine_id}")
    
    # Step 1: Login to GTA5RP
    token = gta5rp_login(login, password)
    if not token:
        logger.error("Failed to login to GTA5RP")
        return False
    
    # Step 2: Get user info
    user_info = get_user_info(token)
    if not user_info:
        logger.error("Failed to get user info")
        return False
    
    logger.info(f"User: {user_info.get('login')}, Balance: {user_info.get('balance')}")
    
    # Step 3: Get all characters
    characters = get_all_characters(token)
    logger.info(f"Found {len(characters)} characters")
    
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
