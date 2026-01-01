import httpx
import socket
from typing import Optional, List, Dict, Any
from config import settings
from utils import get_logger


class APIClient:
    """HTTP клиент для общения с сервером"""
    
    def __init__(self):
        self.base_url = settings.API_URL
        self.client = httpx.AsyncClient(timeout=30)
        self.pc_name = socket.gethostname()
        self.logger = get_logger()
    
    async def heartbeat(
        self,
        status: str = "online",
        current_server: Optional[str] = None,
        current_char: Optional[str] = None,
        ip_status: Optional[str] = None  # allowed, blocked, no_internet
    ) -> Dict[str, Any]:
        """Отправить heartbeat на сервер"""
        try:
            payload = {
                "name": self.pc_name,
                "ip": self._get_external_ip(),
                "status": status,
                "current_server": current_server,
                "current_char": current_char,
                "version": settings.VERSION,
                "ip_status": ip_status,
            }
            
            # Debug: log what we're sending
            self.logger.debug(f"Sending heartbeat: {payload}")
            
            response = await self.client.post(
                f"{self.base_url}/machines/heartbeat",
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Heartbeat failed: {e}")
            return {"commands": []}
    
    async def send_log(self, level: str, message: str, extra: Dict = None):
        """Отправить лог на сервер"""
        try:
            await self.client.post(
                f"{self.base_url}/logs",
                json={
                    "machine_name": self.pc_name,
                    "level": level,
                    "message": message,
                    "extra": extra or {}
                }
            )
        except Exception as e:
            self.logger.error(f"Failed to send log: {e}")
    
    async def complete_command(self, command_id: str, result: str):
        """Отметить команду как выполненную"""
        try:
            await self.client.post(
                f"{self.base_url}/commands/{command_id}/complete",
                json={"result": result}
            )
        except Exception as e:
            self.logger.error(f"Failed to complete command: {e}")
    
    async def fail_command(self, command_id: str, error: str):
        """Отметить команду как failed"""
        try:
            await self.client.post(
                f"{self.base_url}/commands/{command_id}/fail",
                json={"result": error}
            )
        except Exception as e:
            self.logger.error(f"Failed to fail command: {e}")
    
    async def sync_accounts(self, accounts: List[Dict]):
        """Синхронизировать аккаунты с сервером"""
        try:
            response = await self.client.post(
                f"{self.base_url}/accounts/sync",
                params={"machine_name": self.pc_name},
                json=accounts
            )
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to sync accounts: {e}")
            return None
    
    def _get_external_ip(self) -> str:
        """Получить внешний IP"""
        try:
            response = httpx.get("https://api.ipify.org", timeout=5)
            return response.text
        except Exception:
            return "unknown"
    
    async def close(self):
        """Закрыть соединение"""
        await self.client.aclose()
