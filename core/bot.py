import asyncio
from pathlib import Path
from typing import Dict, Any, Callable
from config import settings
from network import APIClient
from core.updater import Updater
from utils import get_logger
from automation.script_runner import ScriptRunner


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
            "run_script": self._cmd_run_script,
            "start_scripts": self._cmd_start_scripts,
            "stop_scripts": self._cmd_stop_scripts,
            "start_debug": self._cmd_start_debug,
            # System commands (for startup scripts)
            "sync_time": self._cmd_sync_time,
            "update_gta_settings": self._cmd_update_gta_settings,
            "fetch_config": self._cmd_fetch_config,
            "sync_profile": self._cmd_sync_profile,
            "close_game": self._cmd_close_game,
        }
        
        # ScriptRunner for automation
        self.script_runner = ScriptRunner(
            data_dir=settings.DATA_DIR,
            api_url=settings.CONFIG_API_URL + "/api"
        )
        
        # Set callback so scripts can call bot commands
        self.script_runner.set_command_callback(self._execute_command_sync)
    
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
        self.logger.info("🔧 Running startup...")
        self.logger.info("=" * 50)
        
        # 1. Sync scripts from server (HARDCODED - always runs to get latest scripts)
        try:
            self.logger.info("📍 Step 1: Sync automation scripts")
            if self.script_runner.sync_from_server():
                self.logger.info("✅ Scripts synced from server")
            else:
                self.logger.warning("⚠️  Scripts sync failed (using cached)")
        except Exception as e:
            self.logger.error(f"Scripts sync error: {e}")
        
        # 2. Run startup scripts (run_on_startup: true)
        # These scripts can call commands: sync_time, update_gta_settings, fetch_config
        try:
            self.logger.info("📍 Step 2: Running startup scripts (run_on_startup)")
            self.script_runner.run_startup_scripts()
            self.logger.info("✅ Startup scripts executed")
        except Exception as e:
            self.logger.error(f"Startup scripts error: {e}")
        
        # 3. Start trigger scanner
        try:
            self.logger.info("📍 Step 3: Starting script trigger scanner")
            self.script_runner.start()
            self.logger.info("✅ Script trigger scanner started")
        except Exception as e:
            self.logger.error(f"Script scanner error: {e}")
        
        self.logger.info("")
        self.logger.info("=" * 50)
        self.logger.info("✅ Startup completed!")
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
        
        # NEW: Check if script exists with this command name
        # Scripts without triggers = manual commands that can override built-in handlers
        if self.script_runner and command in self.script_runner.scripts:
            script = self.script_runner.scripts[command]
            config = script.get('config', {})
            
            # Only use script if it has no automatic triggers (otherwise it's an automation script, not a command)
            has_triggers = bool(config.get('trigger_groups') or config.get('process_triggers'))
            
            if not has_triggers:
                try:
                    self.logger.info(f"🎬 Executing script-based command: '{command}'")
                    success = self.script_runner.execute_script(command)
                    result = "OK" if success else "Script execution failed"
                    await self.api.complete_command(cmd_id, result)
                    self.logger.info(f"✅ Command completed via script: {command}")
                    return
                except Exception as e:
                    self.logger.warning(f"Script execution error, falling back to handler: {e}")
                    # Fall through to hardcoded handler
        
        # Existing: Try hardcoded handler
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
    
    def _execute_command_sync(self, command_name: str, params: dict = None) -> str:
        """Execute a command synchronously (for ScriptRunner call_command action)"""
        import asyncio
        
        params = params or {}
        
        # Handle sync system commands directly (no async needed)
        if command_name == 'sync_time':
            return self._sync_cmd_sync_time()
        elif command_name == 'update_gta_settings':
            return self._sync_cmd_update_gta_settings()
        elif command_name == 'fetch_config':
            return self._sync_cmd_fetch_config()
        
        handler = self.command_handlers.get(command_name)
        
        if not handler:
            self.logger.warning(f"Unknown command for script: {command_name}")
            return f"Unknown command: {command_name}"
        
        try:
            # Get or create event loop for sync execution
            try:
                loop = asyncio.get_running_loop()
                # We're in async context, create a task
                future = asyncio.run_coroutine_threadsafe(handler(params), loop)
                result = future.result(timeout=60)  # 60 sec timeout
            except RuntimeError:
                # No running loop, run directly
                result = asyncio.run(handler(params))
            
            self.logger.info(f"Script command {command_name} completed: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Script command {command_name} failed: {e}")
            return f"Error: {e}"
    
    def _sync_cmd_sync_time(self) -> str:
        """Sync version: Time synchronization"""
        try:
            from scripts.set_local_time import sync_time
            self.logger.info("⏱️ Syncing system time...")
            if sync_time():
                self.logger.info("✅ Time synced successfully")
                return "Time synced"
            else:
                self.logger.warning("⚠️ Time sync failed")
                return "Time sync failed"
        except Exception as e:
            self.logger.error(f"Time sync error: {e}")
            return f"Error: {e}"
    
    def _sync_cmd_update_gta_settings(self) -> str:
        """Sync version: Update GTA settings"""
        try:
            from scripts.update_gta_settings import update_gta_settings
            self.logger.info("🎮 Updating GTA settings...")
            if update_gta_settings():
                self.logger.info("✅ GTA settings updated")
                return "GTA settings updated"
            else:
                self.logger.warning("⚠️ GTA settings update failed")
                return "GTA settings update failed"
        except Exception as e:
            self.logger.error(f"GTA settings error: {e}")
            return f"Error: {e}"
    
    def _sync_cmd_fetch_config(self) -> str:
        """Sync version: Fetch account config"""
        try:
            from scripts.get_config import fetch_config
            self.logger.info("📥 Fetching account config...")
            if fetch_config():
                self.logger.info("✅ Account config fetched")
                return "Config fetched"
            else:
                self.logger.warning("⚠️ Config fetch failed")
                return "Config fetch failed"
        except Exception as e:
            self.logger.error(f"Config fetch error: {e}")
            return f"Error: {e}"
    
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
    
    async def _cmd_run_script(self, params: Dict) -> str:
        """Команда: запустить скрипт по имени"""
        script_name = params.get("script_name", params.get("name", ""))
        if not script_name:
            return "Error: script_name required"
        
        self.logger.info(f"📜 Running script: {script_name}")
        
        try:
            if self.script_runner.execute_script(script_name):
                return f"Script '{script_name}' completed"
            return f"Script '{script_name}' failed"
        except Exception as e:
            return f"Script error: {e}"
    
    async def _cmd_start_scripts(self, params: Dict) -> str:
        """Команда: запустить сканер триггеров"""
        self.logger.info("▶️ Starting scripts scanner")
        self.script_runner.start()
        return "Scripts trigger scanner started"
    
    async def _cmd_stop_scripts(self, params: Dict) -> str:
        """Команда: остановить сканер триггеров"""
        self.logger.info("⏹️ Stopping scripts scanner")
        self.script_runner.stop()
        return "Scripts trigger scanner stopped"
    
    async def _cmd_start_debug(self, params: Dict) -> str:
        """Команда: запустить LogMonitor для дебага"""
        import subprocess
        import sys
        
        self.logger.info("🐛 Starting debug LogMonitor...")
        
        try:
            # Path to log_monitor.py
            log_monitor_path = settings.APP_DIR / "log_monitor.py"
            
            if not log_monitor_path.exists():
                return f"log_monitor.py not found at {log_monitor_path}"
            
            # Start log_monitor.py in new console window
            subprocess.Popen(
                [sys.executable, str(log_monitor_path)],
                cwd=str(settings.APP_DIR),
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            
            return "LogMonitor started (log_monitor.py)"
        except Exception as e:
            self.logger.error(f"Failed to start LogMonitor: {e}")
            return f"Error: {e}"
    
    async def _cmd_sync_time(self, params: Dict) -> str:
        """Синхронизация системного времени"""
        try:
            from scripts.set_local_time import sync_time
            self.logger.info("⏱️ Syncing system time...")
            if sync_time():
                self.logger.info("✅ Time synced successfully")
                return "Time synced"
            else:
                self.logger.warning("⚠️ Time sync failed")
                return "Time sync failed"
        except Exception as e:
            self.logger.error(f"Time sync error: {e}")
            return f"Error: {e}"
    
    async def _cmd_update_gta_settings(self, params: Dict) -> str:
        """Обновить настройки GTA5"""
        try:
            from scripts.update_gta_settings import update_gta_settings
            self.logger.info("🎮 Updating GTA settings...")
            if update_gta_settings():
                self.logger.info("✅ GTA settings updated")
                return "GTA settings updated"
            else:
                self.logger.warning("⚠️ GTA settings update failed")
                return "GTA settings update failed"
        except Exception as e:
            self.logger.error(f"GTA settings error: {e}")
            return f"Error: {e}"
    
    async def _cmd_fetch_config(self, params: Dict) -> str:
        """Получить конфиг аккаунта с сервера"""
        try:
            from scripts.get_config import fetch_config
            self.logger.info("📥 Fetching account config...")
            if fetch_config():
                self.logger.info("✅ Account config fetched")
                return "Config fetched"
            else:
                self.logger.warning("⚠️ Config fetch failed")
                return "Config fetch failed"
        except Exception as e:
            self.logger.error(f"Config fetch error: {e}")
            return f"Error: {e}"
    
    async def _cmd_sync_profile(self, params: Dict) -> str:
        """Синхронизировать профиль GTA5RP с сервером"""
        try:
            from scripts.sync_profile import sync_profile
            
            self.logger.info("📊 Syncing GTA5RP profile...")
            
            # Get account credentials from config
            config = self.script_runner.account_config
            login = config.get('gta_login') or config.get('login')
            password = config.get('gta_password') or config.get('password')
            
            if not login or not password:
                self.logger.error("No GTA5RP credentials in account config")
                return "No credentials"
            
            # Get machine ID from last heartbeat or computer name
            import platform
            machine_id = str(getattr(self, 'machine_id', None) or platform.node())
            
            success = sync_profile(
                login=login,
                password=password,
                server_api_url=settings.CONFIG_API_URL,
                machine_id=machine_id
            )
            
            if success:
                self.logger.info("✅ Profile synced successfully")
                return "Profile synced"
            else:
                self.logger.warning("⚠️ Profile sync failed")
                return "Sync failed"
        except Exception as e:
            self.logger.error(f"Profile sync error: {e}")
            return f"Error: {e}"
    
    async def _cmd_close_game(self, params: Dict) -> str:
        """Команда: закрыть игру и все связанные процессы"""
        import subprocess
        import time
        
        self.logger.info("🎮 Closing game and related processes...")
        
        # Список процессов для завершения
        processes_to_kill = [
            "GTA5.exe",        # GTA 5
            "PlayGTAV.exe",    # GTA 5 Launcher
            "ragemp_v.exe",    # RageMP
            "ragemp.exe",      # RageMP Launcher
            "rage_bootstrapper_launcher.exe",  # RageMP Bootstrapper
            "EpicGamesLauncher.exe",           # Epic Games
            "EpicWebHelper.exe",               # Epic Web Helper
            "RockstarErrorHandler.exe",        # Rockstar Error Handler
            "Rockstar-Launcher-Bootstrapper.exe",  # Rockstar Bootstrapper
            "RockstarService.exe",             # Rockstar Service  
            "Launcher.exe",                    # Generic launcher
            "SocialClubHelper.exe",            # Social Club
        ]
        
        def is_process_running(proc_name: str) -> bool:
            """Проверяет, запущен ли процесс"""
            try:
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {proc_name}"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return proc_name.lower() in result.stdout.lower()
            except:
                return False
        
        def kill_process_taskkill(proc_name: str) -> bool:
            """Убить через taskkill /F"""
            try:
                result = subprocess.run(
                    ["taskkill", "/F", "/IM", proc_name, "/T"],
                    capture_output=True, text=True, timeout=5
                )
                return result.returncode == 0
            except:
                return False
        
        def kill_process_wmic(proc_name: str) -> bool:
            """Убить через wmic (альтернативный метод)"""
            try:
                result = subprocess.run(
                    ["wmic", "process", "where", f"name='{proc_name}'", "delete"],
                    capture_output=True, text=True, timeout=10
                )
                return "deleted" in result.stdout.lower() or result.returncode == 0
            except:
                return False
        
        def kill_process_powershell(proc_name: str) -> bool:
            """Убить через PowerShell (самый агрессивный метод)"""
            try:
                # Убираем .exe для Get-Process
                name_no_ext = proc_name.replace('.exe', '').replace('.EXE', '')
                cmd = f"Get-Process -Name '{name_no_ext}' -ErrorAction SilentlyContinue | Stop-Process -Force"
                result = subprocess.run(
                    ["powershell", "-Command", cmd],
                    capture_output=True, text=True, timeout=10
                )
                return True  # PowerShell не возвращает ошибку если процесса нет
            except:
                return False
        
        def aggressive_kill(proc_name: str) -> bool:
            """Пробует все методы убийства процесса"""
            # Метод 1: taskkill
            if kill_process_taskkill(proc_name):
                return True
            
            # Метод 2: wmic  
            if kill_process_wmic(proc_name):
                return True
            
            # Метод 3: PowerShell
            if kill_process_powershell(proc_name):
                return True
            
            return False
        
        killed = []
        
        # Первый проход - пытаемся убить все процессы через taskkill
        self.logger.info("📍 Pass 1: Killing processes (taskkill)...")
        for proc in processes_to_kill:
            if kill_process_taskkill(proc):
                killed.append(proc)
                self.logger.info(f"  ✅ Killed: {proc}")
        
        # Ждём немного
        time.sleep(1)
        
        # Второй проход - проверяем и добиваем через wmic
        still_running = [p for p in processes_to_kill if is_process_running(p)]
        if still_running:
            self.logger.info("📍 Pass 2: Killing remaining via wmic...")
            for proc in still_running:
                self.logger.warning(f"  ⚠️ Still running: {proc}")
                if kill_process_wmic(proc):
                    killed.append(f"{proc}(wmic)")
                    self.logger.info(f"  ✅ Killed via wmic: {proc}")
        
        time.sleep(0.5)
        
        # Третий проход - PowerShell для самых упрямых
        still_running = [p for p in processes_to_kill if is_process_running(p)]
        if still_running:
            self.logger.info("📍 Pass 3: Killing remaining via PowerShell...")
            for proc in still_running:
                self.logger.warning(f"  ⚠️ Still alive: {proc}, using PowerShell...")
                kill_process_powershell(proc)
                time.sleep(0.3)
                if not is_process_running(proc):
                    killed.append(f"{proc}(ps)")
                    self.logger.info(f"  ✅ Killed via PowerShell: {proc}")
                else:
                    self.logger.error(f"  ❌ Could not kill: {proc}")
        
        # Финальная проверка
        time.sleep(0.5)
        final_remaining = [p for p in processes_to_kill if is_process_running(p)]
        if final_remaining:
            self.logger.warning(f"⚠️ Survivors: {', '.join(final_remaining)}")
        
        # Сбросить статус на online
        self.status = "online"
        self.current_server = None
        
        # Убираем дубликаты из списка
        unique_killed = set()
        for p in killed:
            clean_name = p.replace('(wmic)', '').replace('(ps)', '')
            unique_killed.add(clean_name)
        
        if unique_killed:
            self.logger.info(f"✅ Closed {len(unique_killed)} processes")
            return f"Closed: {', '.join(unique_killed)}"
        else:
            self.logger.info("ℹ️ No game processes were running")
            return "No game processes found"
    
    def stop(self):
        """Остановить бота"""
        self.script_runner.stop()
        self.running = False
