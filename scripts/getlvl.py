import json
import subprocess
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional
import sys
import time

try:
    import requests
except ImportError:
    print("Installing required libraries...", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

# Configuration
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
REQUEST_TIMEOUT = 30

server_names = {
    1: "01.Downtown",
    2: "02.Strawberry",
    3: "03.Vinewood",
    4: "04.Blackberry",
    5: "05.Insquad",
    6: "06.Sunrise",
    7: "07.Rainbow",
    8: "08.Richman",
    9: "09.Eclipse",
    10: "10.LaMesa",
    11: "11.Burton",
    12: "12.Rockford",
    13: "13.Alta",
    14: "14.DelPerro",
    15: "15.Davis",
    16: "16.Harmony",
    17: "17.Redwood",
    18: "18.Hawick",
    19: "19.Grapeseed",
    20: "20.Murrieta",
    21: "21.Vespucci",
    22: "22.Milton",
    23: "23.LaPuerta"  # NEW: 23rd server
}


@dataclass
class Profile:
    is_online: bool
    name: str
    server: str
    lvl: int
    exp: int
    max_exp: int
    cash: int
    bank: int
    house: bool
    apartment: bool
    vehicles: bool
    hours_played: int
    vip_level: int
    vip_name: str
    vip_expire_at: int


def from_dict(data: dict, server_name: str) -> Profile:
    # Remove unnecessary fields
    keys_to_remove = ["age", "id", "sex", "fraction", "fraction_rank", "fraction_rank_name", "friends",
                      "skills", "is_vehicle_view_needed", "business"]
    for key in keys_to_remove:
        data.pop(key, None)

    # Convert to boolean
    data["house"] = bool(data.get("house"))
    data["apartment"] = bool(data.get("apartment"))
    data["vehicles"] = bool(data.get("vehicles"))

    data["server"] = server_name
    return Profile(**data)


def api_login(login: str, password: str) -> Optional[str]:
    """Login to GTA5RP API with retry logic. Returns token or None."""
    url = "https://gta5rp.com/api/V2/users/auth/login"
    payload = json.dumps({
        "login": login,
        "password": password,
        "remember": "0"
    })
    headers = {'content-type': "application/json"}
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(url, data=payload, headers=headers, timeout=REQUEST_TIMEOUT)
            
            # Check HTTP status
            if response.status_code != 200:
                print(f"[Attempt {attempt}/{MAX_RETRIES}] HTTP {response.status_code}", flush=True)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                    continue
                return None
            
            # Check for empty response
            if not response.text or response.text.strip() == "":
                print(f"[Attempt {attempt}/{MAX_RETRIES}] Empty response from API", flush=True)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                    continue
                return None
            
            # Parse JSON
            try:
                account = json.loads(response.text)
            except json.JSONDecodeError as e:
                print(f"[Attempt {attempt}/{MAX_RETRIES}] JSON error: {e}", flush=True)
                print(f"Response: {response.text[:100]}...", flush=True)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                    continue
                return None
            
            # Check for token
            if "token" not in account:
                # Check for error message
                if "message" in account:
                    print(f"API Error: {account['message']}", flush=True)
                else:
                    print(f"[Attempt {attempt}/{MAX_RETRIES}] No token in response", flush=True)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                    continue
                return None
            
            return account["token"]
            
        except requests.exceptions.Timeout:
            print(f"[Attempt {attempt}/{MAX_RETRIES}] Timeout", flush=True)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
        except requests.exceptions.ConnectionError:
            print(f"[Attempt {attempt}/{MAX_RETRIES}] Connection error", flush=True)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
        except requests.exceptions.RequestException as e:
            print(f"[Attempt {attempt}/{MAX_RETRIES}] Request error: {e}", flush=True)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    
    return None


def get_profiles(login: str, password: str) -> List[Profile]:
    """Get all profiles for user."""
    
    # Login with retry
    token = api_login(login, password)
    if not token:
        print("Failed to login after all retries", flush=True)
        return []
    
    profiles: List[Profile] = []
    
    # Get profiles from all servers
    for server_id in range(1, 24):  # Updated: 1-23 servers
        url = f"https://gta5rp.com/api/V2/users/chars/{server_id}"
        headers = {'x-access-token': token}
        
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            
            # Skip non-200 responses
            if response.status_code != 200:
                continue
            
            # Skip empty responses
            if not response.text or response.text.strip() in ("", "[]", "null"):
                continue
            
            # Parse JSON
            try:
                json_data = json.loads(response.text)
            except json.JSONDecodeError:
                continue
            
            # Skip if not a list or empty
            if not isinstance(json_data, list) or len(json_data) == 0:
                continue
            
            # Parse profiles
            for data in json_data:
                try:
                    profile = from_dict(data.copy(), server_names.get(server_id, f"Server{server_id}"))
                    profiles.append(profile)
                except Exception as e:
                    print(f"Error parsing profile on server {server_id}: {e}", flush=True)
                    continue
                    
        except requests.exceptions.RequestException:
            continue
    
    return profiles


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: getlvl.py <login> <password>", flush=True)
        sys.exit(0)
    
    login = sys.argv[1]
    password = sys.argv[2]
    
    profiles = get_profiles(login, password)
    
    if not profiles:
        print("No profiles found or API unavailable", flush=True)
        sys.exit(0)
    
    # Find online profile
    for profile in profiles:
        if profile.is_online:
            print(str(profile.lvl), flush=True)
            sys.exit(profile.lvl)
    
    print("No online profile found", flush=True)
    sys.exit(0)
