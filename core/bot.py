import asyncio
from typing import Dict, Any, Callable
from config import settings
from network import APIClient
from core.updater import Updater
from utils import get_logger


class VirtBot:
    """Главный класс бота"""
    
    def __init__(self):
        self.logger = get_logger()
        self.api = APIClient()
        self.updater = Updater()
        self.running = True
        
        # Текущее состояние
        self.status = "online"
        self.current_server = None
        self.current_char = None
        
        # Обработчики команд
        self.command_handlers: Dict[str, Callable] = {
            "update": self._cmd_update,
            "restart": self._cmd_restart,
            "screenshot": self._cmd_screenshot,
            "reboot_pc": self._cmd_reboot,
            "run_roulette": self._cmd_roulette,
            "stop_roulette": self._cmd_stop_roulette,
            "sync_accounts": self._cmd_sync_accounts,
            "join_server": self._cmd_join_server,
            "stop_bot": self._cmd_stop_bot,
        }
    
    async def run(self):
        """Главный цикл"""
        self.logger.info(f"🚀 VirtBot v{settings.VERSION} starting...")
        
        # Проверка обновлений при старте
        if self.updater.check_update():
            self.updater.update_and_restart()
            return
        
        self.logger.info("✅ Bot started successfully")
        await self.api.send_log("info", "Bot started")
        
        # Запуск startup скриптов если можно фармить
        can_farm = getattr(self, 'can_farm', False)
        if can_farm:
            await self._run_startup_scripts()
        
        # Запуск фоновых задач
        tasks = [
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._update_check_loop()),
            # asyncio.create_task(self._game_loop()),  # TODO: добавить позже
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            self.logger.info("Bot tasks cancelled")
        finally:
            await self.api.close()
    
    async def _run_startup_scripts(self):
        """Запуск скриптов инициализации"""
        self.logger.info("")
        self.logger.info("=" * 50)
        self.logger.info("🔧 Running startup scripts...")
        self.logger.info("=" * 50)
        
        # 1. Синхронизация времени
        try:
            from scripts.set_local_time import sync_time
            self.logger.info("📍 Step 1: Time sync")
            if sync_time():
                self.logger.info("✅ Time synced")
            else:
                self.logger.warning("⚠️  Time sync failed (continuing)")
        except Exception as e:
            self.logger.error(f"Time sync error: {e}")
        
        # 2. Настройки GTA
        try:
            from scripts.update_gta_settings import update_gta_settings
            self.logger.info("📍 Step 2: GTA settings")
            if update_gta_settings():
                self.logger.info("✅ GTA settings updated")
            else:
                self.logger.warning("⚠️  GTA settings failed (continuing)")
        except Exception as e:
            self.logger.error(f"GTA settings error: {e}")
        
        # 3. Получение конфига аккаунта
        try:
            from scripts.get_config import fetch_config
            self.logger.info("📍 Step 3: Fetch account config")
            if fetch_config():
                self.logger.info("✅ Account config fetched")
            else:
                self.logger.warning("⚠️  Config fetch failed (continuing)")
        except Exception as e:
            self.logger.error(f"Config fetch error: {e}")
        
        # Note: Server connection через реестр Windows при вызове join_server
        # Больше не нужно обновлять storage.json при старте
        
        self.logger.info("")
        self.logger.info("=" * 50)
        self.logger.info("✅ Startup scripts completed!")
        self.logger.info("=" * 50)
        self.logger.info("")
    
    async def _heartbeat_loop(self):
        """Отправка heartbeat каждые N секунд"""
        while self.running:
            try:
                # Получаем ip_status если он установлен в main.py
                ip_status = getattr(self, 'ip_status', None)
                ip_status_str = ip_status.value if ip_status else None
                
                response = await self.api.heartbeat(
                    status=self.status,
                    current_server=self.current_server,
                    current_char=self.current_char,
                    ip_status=ip_status_str
                )
                
                # Обработка команд из ответа
                for cmd in response.get("commands", []):
                    await self._execute_command(cmd)
                    
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")
            
            await asyncio.sleep(settings.HEARTBEAT_INTERVAL)
    
    async def _update_check_loop(self):
        """Проверка обновлений"""
        while self.running:
            await asyncio.sleep(settings.UPDATE_CHECK_INTERVAL)
            
            if self.updater.check_update():
                self.logger.info("Update found, restarting...")
                await self.api.send_log("info", "Updating and restarting")
                self.updater.update_and_restart()
    
    async def _execute_command(self, cmd: Dict[str, Any]):
        """Выполнение команды от сервера"""
        command = cmd.get("command")
        params = cmd.get("params", {})
        cmd_id = cmd.get("id")
        
        self.logger.info(f"📨 Received command: {command}")
        
        handler = self.command_handlers.get(command)
        if handler:
            try:
                result = await handler(params)
                await self.api.complete_command(cmd_id, result or "OK")
                self.logger.info(f"✅ Command completed: {command}")
            except Exception as e:
                error = str(e)
                await self.api.fail_command(cmd_id, error)
                self.logger.error(f"❌ Command failed: {command} - {error}")
        else:
            await self.api.fail_command(cmd_id, f"Unknown command: {command}")
            self.logger.warning(f"⚠️ Unknown command: {command}")
    
    # ==================== COMMAND HANDLERS ====================
    
    async def _cmd_update(self, params: Dict) -> str:
        """Команда: обновить бота"""
        self.updater.update_and_restart()
        return "Updating..."
    
    async def _cmd_restart(self, params: Dict) -> str:
        """Команда: перезапустить бота"""
        import subprocess
        import sys
        from config import APP_DIR
        
        # Запускаем батник и закрываем текущий процесс
        bat_file = APP_DIR / "restart.bat"
        subprocess.Popen(["cmd", "/c", str(bat_file)], creationflags=subprocess.CREATE_NEW_CONSOLE)
        sys.exit(0)
        return "Restarting..."
    
    async def _cmd_screenshot(self, params: Dict) -> str:
        """Команда: сделать скриншот"""
        from automation.screen import ScreenCapture
        screen = ScreenCapture()
        path = screen.take_screenshot()
        return f"Screenshot saved: {path}"
    
    async def _cmd_reboot(self, params: Dict) -> str:
        """Команда: перезагрузить ПК"""
        import subprocess
        subprocess.run(["shutdown", "/r", "/t", "60", "/c", "VirtBot reboot"])
        return "Rebooting in 60 seconds"
    
    async def _cmd_roulette(self, params: Dict) -> str:
        """Команда: запустить рулетку"""
        # TODO: реализовать
        return "Roulette started"
    
    async def _cmd_stop_roulette(self, params: Dict) -> str:
        """Команда: остановить рулетку"""
        # TODO: реализовать
        return "Roulette stopped"
    
    async def _cmd_sync_accounts(self, params: Dict) -> str:
        """Команда: синхронизировать аккаунты"""
        from game.gta5rp_api import GTA5RPAPI
        gta = GTA5RPAPI()
        
        if await gta.login(settings.GTA5RP_LOGIN, settings.GTA5RP_PASSWORD):
            profiles = await gta.get_profiles()
            accounts = [p.to_dict() for p in profiles]
            result = await self.api.sync_accounts(accounts)
            return f"Synced: {result}"
        return "Failed to login to GTA5RP"
    
    async def _cmd_join_server(self, params: Dict) -> str:
        """
        Команда: зайти на сервер
        Использует Windows Registry для прямого подключения (без кликов!)
        """
        self.logger.info("🎮 Join server command received")
        
        try:
            from game.launcher import launch_and_connect
            
            if launch_and_connect():
                self.status = "gaming"
                return "Game launched and connecting to server!"
            return "Failed to launch game"
            
        except Exception as e:
            self.logger.error(f"Launcher error: {e}")
            return f"Launch error: {e}"
    
    async def _cmd_stop_bot(self, params: Dict) -> str:
        """Команда: остановить бота"""
        self.logger.info("🛑 Stop command received")
        self.stop()
        return "Bot stopping..."
    
    def stop(self):
        """Остановить бота"""
        self.running = False
