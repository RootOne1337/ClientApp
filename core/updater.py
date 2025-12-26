import subprocess
import sys
import os
import shutil
import tempfile
from pathlib import Path
from config import APP_DIR, settings
from utils import get_logger

# Пробуем импортировать httpx синхронно (для обновлений до запуска async loop)
try:
    import httpx
except ImportError:
    httpx = None


class Updater:
    """
    Автообновление клиента.
    Поддерживает два режима:
    1. Git mode (для разработки) — git pull
    2. EXE mode (для продакшена) — скачивание нового exe с сервера
    """
    
    def __init__(self):
        self.logger = get_logger()
        self.app_dir = APP_DIR
        self.is_frozen = getattr(sys, 'frozen', False)  # True если запущен как exe
        self.current_version = settings.VERSION
    
    def check_update(self) -> bool:
        """Проверить есть ли обновления"""
        if self.is_frozen:
            return self._check_update_api()
        else:
            return self._check_update_git()
    
    def update_and_restart(self):
        """Обновить и перезапустить"""
        if self.is_frozen:
            self._update_exe()
        else:
            self._update_git()
    
    # ==================== API Mode (EXE) ====================
    
    def _check_update_api(self) -> bool:
        """Проверить обновления через API сервера"""
        if not httpx:
            return False
        
        try:
            response = httpx.post(
                f"{settings.API_URL}/client/version/check",
                json={"current_version": self.current_version},
                timeout=30
            )
            data = response.json()
            
            if data.get("update_available"):
                self.logger.info(f"🔄 Update available: {self.current_version} → {data['version']}")
                self._new_version_info = data
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"API update check failed: {e}")
            return False
    
    def _update_exe(self):
        """Скачать новый exe и заменить себя"""
        if not hasattr(self, '_new_version_info'):
            self.logger.error("No version info for update")
            return
        
        info = self._new_version_info
        download_url = info.get("download_url")
        
        if not download_url:
            self.logger.error("No download URL provided")
            return
        
        try:
            self.logger.info(f"📥 Downloading update from {download_url}...")
            
            # Скачиваем во временный файл
            with tempfile.NamedTemporaryFile(delete=False, suffix=".exe") as tmp_file:
                tmp_path = tmp_file.name
                
                with httpx.stream("GET", download_url, timeout=300) as response:
                    response.raise_for_status()
                    for chunk in response.iter_bytes():
                        tmp_file.write(chunk)
            
            self.logger.info("✅ Download complete, preparing update...")
            
            # Путь к текущему exe
            current_exe = sys.executable
            backup_exe = current_exe + ".bak"
            
            # Создаём батник для замены exe после закрытия приложения
            # (Windows не позволяет заменить работающий exe)
            update_script = self._create_update_script(tmp_path, current_exe, backup_exe)
            
            self.logger.info("🔄 Restarting with new version...")
            
            # Запускаем скрипт обновления и закрываем текущее приложение
            subprocess.Popen(
                ["cmd", "/c", update_script],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            sys.exit(0)
            
        except Exception as e:
            self.logger.error(f"EXE update failed: {e}")
            if 'tmp_path' in locals():
                try:
                    os.unlink(tmp_path)
                except:
                    pass
    
    def _create_update_script(self, new_exe: str, current_exe: str, backup_exe: str) -> str:
        """Создать bat-скрипт для обновления"""
        script_path = os.path.join(tempfile.gettempdir(), "virtbot_update.bat")
        
        script = f'''@echo off
ping 127.0.0.1 -n 3 > nul
del /f /q "{backup_exe}" 2>nul
move /y "{current_exe}" "{backup_exe}"
move /y "{new_exe}" "{current_exe}"
start "" "{current_exe}"
del /f /q "{backup_exe}" 2>nul
del "%~f0"
'''
        
        with open(script_path, 'w') as f:
            f.write(script)
        
        return script_path
    
    # ==================== Git Mode (Development) ====================
    
    def _check_update_git(self) -> bool:
        """Проверить есть ли обновления в git"""
        try:
            subprocess.run(
                ["git", "fetch"],
                cwd=self.app_dir,
                capture_output=True,
                timeout=30
            )
            
            result = subprocess.run(
                ["git", "status", "-uno"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            has_updates = "Your branch is behind" in result.stdout
            if has_updates:
                self.logger.info("🔄 Git updates available!")
            
            return has_updates
            
        except subprocess.TimeoutExpired:
            self.logger.warning("Git fetch timeout")
            return False
        except Exception as e:
            self.logger.error(f"Git update check failed: {e}")
            return False
    
    def _update_git(self):
        """Обновить код через git и перезапустить"""
        try:
            self.logger.info("📥 Starting update via batch file...")
            
            # Запускаем батник обновления и закрываем текущий процесс
            bat_file = self.app_dir / "update.bat"
            subprocess.Popen(["cmd", "/c", str(bat_file)], creationflags=subprocess.CREATE_NEW_CONSOLE)
            sys.exit(0)
            
        except Exception as e:
            self.logger.error(f"Git update failed: {e}")
    
    # ==================== Utils ====================
    
    def get_current_version(self) -> str:
        """Получить текущую версию"""
        if self.is_frozen:
            return self.current_version
        
        # Для dev mode - коммит git
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            return f"{self.current_version}-{result.stdout.strip()}"
        except Exception:
            return self.current_version
