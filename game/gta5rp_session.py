"""
GTA5RP Session Manager
Manages authentication tokens and reduces API calls.

Key features:
- Token caching (valid ~30 days with remember=1)
- Auto re-login on 401 errors
- Server-specific character queries
"""
import json
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List
from config import DATA_DIR
from utils import get_logger

logger = get_logger(__name__)

# Session cache file
SESSION_FILE = DATA_DIR / "gta5rp_session.json"

# GTA5RP API
GTA5RP_API = "https://gta5rp.com/api/V2"

# Server mapping (updated with 23rd server)
SERVER_NAMES = {
    1: "01.Downtown", 2: "02.Strawberry", 3: "03.Vinewood", 4: "04.Blackberry",
    5: "05.Insquad", 6: "06.Sunrise", 7: "07.Rainbow", 8: "08.Richman",
    9: "09.Eclipse", 10: "10.LaMesa", 11: "11.Burton", 12: "12.Rockford",
    13: "13.Alta", 14: "14.DelPerro", 15: "15.Davis", 16: "16.Harmony",
    17: "17.Redwood", 18: "18.Hawick", 19: "19.Grapeseed", 20: "20.Murrieta",
    21: "21.Vespucci", 22: "22.Milton", 23: "23.LaPuerta"
}

SERVER_IDS = {v: k for k, v in SERVER_NAMES.items()}


class GTA5RPSession:
    """Manages GTA5RP authentication and API calls with token caching"""
    
    def __init__(self):
        self.token = None
        self.login = None
        self.password = None
        self._load_session()
    
    def _load_session(self):
        """Load cached session from disk"""
        if not SESSION_FILE.exists():
            return
        
        try:
            with open(SESSION_FILE, 'r') as f:
                data = json.load(f)
                self.token = data.get("token")
                self.login = data.get("login")
                
                # No TTL check - token valid until API returns 401
                if self.token:
                    logger.info(f"Loaded cached token for {self.login}")
        except Exception as e:
            logger.warning(f"Failed to load session: {e}")
    
    def _save_session(self):
        """Save session to disk"""
        try:
            SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SESSION_FILE, 'w') as f:
                json.dump({
                    "token": self.token,
                    "login": self.login
                }, f)
        except Exception as e:
            logger.warning(f"Failed to save session: {e}")
    
    def login_if_needed(self, login: str, password: str, force: bool = False) -> bool:
        """
        Login to GTA5RP if token is missing.
        Uses remember=1 for long-lived token (~30 days).
        Returns True if we have a valid token.
        """
        # Check if we have a cached token
        if not force and self.token:
            logger.info("Using cached token")
            return True
        
        # Login with remember=1 for long-lived token
        try:
            url = f"{GTA5RP_API}/users/auth/login"
            payload = {"login": login, "password": password, "remember": "1"}  # ✅ Remember me!
            
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if "token" not in data:
                logger.error(f"Login failed: {data}")
                return False
            
            self.token = data["token"]
            self.login = login
            self.password = password
            
            # Save to disk
            self._save_session()
            
            logger.info(f"✓ Logged in as {login} (remember=1, token valid ~30 days)")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Login error: {e}")
            return False
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Get user account info"""
        if not self.token:
            return None
        
        try:
            url = f"{GTA5RP_API}/users/"
            headers = {"x-access-token": self.token}
            
            response = requests.get(url, headers=headers, timeout=30)
            
            # Token expired?
            if response.status_code == 401:
                logger.warning("Token expired (401), re-login needed")
                self.token = None
                return None
            
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Get user info error: {e}")
            return None
    
    def get_characters_for_server(self, server_name: str) -> List[Dict[str, Any]]:
        """
        Get characters for a SPECIFIC server only.
        Returns empty list if server not found or error.
        """
        if not self.token:
            return []
        
        # Convert server name to ID
        server_id = SERVER_IDS.get(server_name)
        if not server_id:
            logger.error(f"Unknown server: {server_name}")
            return []
        
        try:
            url = f"{GTA5RP_API}/users/chars/{server_id}"
            headers = {"x-access-token": self.token}
            
            response = requests.get(url, headers=headers, timeout=15)
            
            # Token expired?
            if response.status_code == 401:
                logger.warning("Token expired (401), re-login needed")
                self.token = None
                return []
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            if not isinstance(data, list):
                return []
            
            # Add server info to each character
            for char in data:
                char["server_id"] = server_id
                char["server_name"] = server_name
            
            return data
            
        except requests.RequestException as e:
            logger.error(f"Get characters error: {e}")
            return []


# Global session instance
_session = None

def get_session() -> GTA5RPSession:
    """Get or create global session"""
    global _session
    if _session is None:
        _session = GTA5RPSession()
    return _session
