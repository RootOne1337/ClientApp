import httpx
from dataclasses import dataclass, asdict
from typing import List, Optional
import time
from utils import get_logger


@dataclass
class Profile:
    """Профиль персонажа GTA5RP"""
    name: str
    server: str
    lvl: int
    exp: int
    money: int  # cash + bank
    vip_type: str
    vip_days: int
    has_apartment: bool
    has_house: bool
    is_online: bool
    
    def to_dict(self) -> dict:
        return {
            "server": self.server,
            "nickname": self.name,
            "lvl": self.lvl,
            "money": self.money,
            "vip_type": self.vip_type,
            "vip_days": self.vip_days,
            "has_apartment": self.has_apartment,
        }


class GTA5RPAPI:
    """API клиент для gta5rp.com"""
    
    BASE_URL = "https://gta5rp.com/api/V2"
    
    SERVERS = {
        1: "01.Downtown", 2: "02.Strawberry", 3: "03.Vinewood",
        4: "04.Blackberry", 5: "05.Insquad", 6: "06.Sunrise",
        7: "07.Rainbow", 8: "08.Richman", 9: "09.Eclipse",
        10: "10.LaMesa", 11: "11.Burton", 12: "12.Rockford",
        13: "13.Alta", 14: "14.DelPerro", 15: "15.Davis",
        16: "16.Harmony", 17: "17.Redwood", 18: "18.Hawick",
        19: "19.Grapeseed", 20: "20.Murrieta", 21: "21.Vespucci",
        22: "22.Milton"
    }
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30)
        self.token: Optional[str] = None
        self.logger = get_logger()
    
    async def login(self, login: str, password: str) -> bool:
        """Авторизация и получение токена"""
        try:
            response = await self.client.post(
                f"{self.BASE_URL}/users/auth/login",
                json={"login": login, "password": password, "remember": "0"}
            )
            data = response.json()
            
            if "token" in data:
                self.token = data["token"]
                self.logger.info("✅ GTA5RP login successful")
                return True
            else:
                self.logger.error(f"GTA5RP login failed: {data.get('message', 'Unknown error')}")
                return False
                
        except Exception as e:
            self.logger.error(f"GTA5RP login error: {e}")
            return False
    
    async def get_profiles(self) -> List[Profile]:
        """Получить все профили со всех серверов"""
        if not self.token:
            self.logger.error("Not logged in to GTA5RP")
            return []
        
        profiles = []
        
        for server_id, server_name in self.SERVERS.items():
            try:
                response = await self.client.get(
                    f"{self.BASE_URL}/users/chars/{server_id}",
                    headers={"x-access-token": self.token}
                )
                
                if response.status_code != 200:
                    continue
                
                data = response.json()
                if not isinstance(data, list):
                    continue
                
                for char in data:
                    profiles.append(Profile(
                        name=char.get("name", ""),
                        server=server_name,
                        lvl=char.get("lvl", 1),
                        exp=char.get("exp", 0),
                        money=char.get("cash", 0) + char.get("bank", 0),
                        vip_type=self._get_vip_type(char.get("vip_level", 0)),
                        vip_days=self._calc_vip_days(char.get("vip_expire_at", 0)),
                        has_apartment=bool(char.get("apartment")),
                        has_house=bool(char.get("house")),
                        is_online=char.get("is_online", False)
                    ))
                    
            except Exception as e:
                self.logger.error(f"Error fetching server {server_name}: {e}")
                continue
        
        self.logger.info(f"📊 Found {len(profiles)} profiles")
        return profiles
    
    async def get_user_info(self) -> Optional[dict]:
        """Получить информацию о пользователе"""
        if not self.token:
            return None
        
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/users/",
                headers={"x-access-token": self.token}
            )
            return response.json()
        except Exception as e:
            self.logger.error(f"Error getting user info: {e}")
            return None
    
    def _get_vip_type(self, level: int) -> str:
        """Получить тип VIP по уровню"""
        return {0: "", 1: "Standart", 2: "Gold", 3: "Platinum"}.get(level, "")
    
    def _calc_vip_days(self, expire_at: int) -> int:
        """Рассчитать дни до окончания VIP"""
        if not expire_at:
            return 0
        days = (expire_at - time.time()) / 86400
        return max(0, int(days))
    
    async def close(self):
        """Закрыть соединение"""
        await self.client.aclose()
