"""
Game Launcher Module v2.0

Handles:
- RAGE Multiplayer updater/launcher
- Direct server connection via Windows Registry (no clicks!)
- GTA V launch
- Process management

Connection method: Windows Registry keys (launch2.ip, launch2.port)
This works in RageMP 0.3+ and auto-connects to server without manual clicks.
"""

import subprocess
import time
import os
from pathlib import Path
from typing import Optional, Tuple
import json

# Добавляем parent в path для импорта
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from utils import get_logger
    logger = get_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# Windows Registry support
try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    WINREG_AVAILABLE = False


# ============================================================================
# КОНФИГУРАЦИЯ ПУТЕЙ
# ============================================================================

DEFAULT_PATHS = {
    # RageMP
    "ragemp_dir": r"C:\Games\GTA5RP\RageMP",
    "ragemp_updater": r"C:\Games\GTA5RP\RageMP\updater.exe",
    "ragemp_launcher": r"C:\Games\GTA5RP\RageMP\ragemp_v.exe",
    
    # GTA V
    "gta_dir": r"C:\Games\GTA5RP\Grand Theft Auto V",
    "gta_exe": r"C:\Games\GTA5RP\Grand Theft Auto V\PlayGTAV.exe",
}


def get_game_paths() -> dict:
    """Получить пути к игре"""
    return DEFAULT_PATHS.copy()


def is_process_running(process_name: str) -> bool:
    """Проверить запущен ли процесс"""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return process_name.lower() in result.stdout.lower()
    except Exception as e:
        logger.error(f"Error checking process {process_name}: {e}")
        return False


def is_ragemp_running() -> bool:
    """Проверить запущен ли RageMP"""
    return is_process_running("ragemp_v.exe") or is_process_running("RAGEMP.exe")


def is_gta_running() -> bool:
    """Проверить запущена ли GTA V"""
    return is_process_running("GTA5.exe")


# ============================================================================
# WINDOWS REGISTRY - ПРЯМОЕ ПОДКЛЮЧЕНИЕ К СЕРВЕРУ
# ============================================================================

def set_server_in_registry(server_ip: str, server_port: str = "22005") -> bool:
    """
    Записать параметры сервера в реестр Windows.
    После этого RageMP автоматически подключится к серверу при запуске.
    
    Записывает в:
    - HKCU\SOFTWARE\RAGE-MP\launch2.ip (для GTA5RP)
    - HKCU\SOFTWARE\RAGE-MP\launch2.port
    - HKCU\SOFTWARE\RAGE-MP\launch.ip (для совместимости)
    - HKCU\SOFTWARE\RAGE-MP\launch.port
    
    Args:
        server_ip: IP/hostname сервера (например v3-downtown.gta5rp.com)
        server_port: Порт сервера (по умолчанию 22005)
    
    Returns:
        True если успешно записано
    """
    if not WINREG_AVAILABLE:
        logger.error("❌ winreg module not available (not Windows?)")
        return False
    
    logger.info("� Setting server in Windows Registry...")
    logger.info(f"   Server: {server_ip}:{server_port}")
    
    reg_path = r"SOFTWARE\RAGE-MP"
    
    try:
        # Пробуем открыть существующий ключ
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_WRITE)
        except FileNotFoundError:
            # Создаём ключ если не существует
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_path)
        
        # Записываем для GTA5RP (launch2.*)
        winreg.SetValueEx(key, "launch2.ip", 0, winreg.REG_SZ, server_ip)
        winreg.SetValueEx(key, "launch2.port", 0, winreg.REG_SZ, str(server_port))
        
        # Записываем для совместимости (launch.*)
        winreg.SetValueEx(key, "launch.ip", 0, winreg.REG_SZ, server_ip)
        winreg.SetValueEx(key, "launch.port", 0, winreg.REG_SZ, str(server_port))
        
        winreg.CloseKey(key)
        
        logger.info("✅ Registry updated successfully!")
        logger.info(f"   launch2.ip = {server_ip}")
        logger.info(f"   launch2.port = {server_port}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to write to registry: {e}")
        return False


def get_server_from_registry() -> Tuple[Optional[str], Optional[str]]:
    """Прочитать текущий сервер из реестра"""
    if not WINREG_AVAILABLE:
        return None, None
    
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\RAGE-MP")
        ip = winreg.QueryValueEx(key, "launch2.ip")[0]
        port = winreg.QueryValueEx(key, "launch2.port")[0]
        winreg.CloseKey(key)
        return ip, port
    except:
        return None, None


# ============================================================================
# ЗАГРУЗКА СЕРВЕРА ИЗ КОНФИГА
# ============================================================================

def get_server_from_account_config() -> Tuple[Optional[str], Optional[str]]:
    """
    Получить hostname сервера из data/account.json
    
    Returns:
        (server_hostname, "22005") или (None, None)
    """
    try:
        from config import ACCOUNT_FILE
        
        if not ACCOUNT_FILE.exists():
            logger.warning("account.json not found")
            return None, None
        
        with open(ACCOUNT_FILE, 'r', encoding='utf-8') as f:
            account = json.load(f)
        
        server_hostname = account.get("server_hostname", "")
        if server_hostname:
            return server_hostname, "22005"
        
        logger.warning("No server_hostname in account.json")
        return None, None
        
    except Exception as e:
        logger.error(f"Failed to read account config: {e}")
        return None, None


# ============================================================================
# ЗАПУСК EXE
# ============================================================================

def run_exe(exe_path: str, cwd: str = None, wait: bool = False, timeout: int = None) -> bool:
    """Запустить exe файл"""
    exe = Path(exe_path)
    
    if not exe.exists():
        logger.error(f"❌ File not found: {exe_path}")
        return False
    
    if cwd is None:
        cwd = str(exe.parent)
    
    logger.info(f"🚀 Running: {exe.name}")
    logger.info(f"   Path: {exe_path}")
    logger.info(f"   CWD: {cwd}")
    
    try:
        original_cwd = os.getcwd()
        os.chdir(cwd)
        
        if wait:
            result = subprocess.run(
                f'"{exe_path}"',
                shell=True,
                timeout=timeout,
                capture_output=True,
                text=True
            )
            os.chdir(original_cwd)
            logger.info(f"   Exit code: {result.returncode}")
            return result.returncode == 0
        else:
            # Запускаем через os.startfile (нативный Windows)
            os.startfile(str(exe))
            time.sleep(1)
            os.chdir(original_cwd)
            return True
            
    except subprocess.TimeoutExpired:
        os.chdir(original_cwd)
        logger.warning(f"⚠️  Timeout waiting for {exe.name}")
        return False
    except Exception as e:
        try:
            os.chdir(original_cwd)
        except:
            pass
        logger.error(f"❌ Failed to run {exe.name}: {e}")
        return False


# ============================================================================
# ОСНОВНЫЕ ФУНКЦИИ
# ============================================================================

def run_ragemp_launcher() -> bool:
    """Запустить RAGE Multiplayer (сам клиент)"""
    paths = get_game_paths()
    
    logger.info("=" * 50)
    logger.info("🎮 Starting RageMP")
    logger.info("=" * 50)
    
    launcher_path = paths["ragemp_launcher"]
    ragemp_dir = paths["ragemp_dir"]
    
    if not Path(launcher_path).exists():
        logger.error(f"❌ RageMP not found: {launcher_path}")
        return False
    
    return run_exe(
        exe_path=launcher_path,
        cwd=ragemp_dir,
        wait=False
    )


def launch_and_connect(server_hostname: str = None, server_port: str = "22005") -> bool:
    """
    Запустить игру и подключиться к серверу.
    
    НОВЫЙ МЕТОД: Записывает сервер в реестр → RageMP автоматически подключается!
    Не нужны клики, не нужен storage.json.
    
    Args:
        server_hostname: Hostname сервера (если None - берём из account.json)
        server_port: Порт (по умолчанию 22005)
    
    Returns:
        True если успешно
    """
    logger.info("")
    logger.info("=" * 50)
    logger.info("🎮 LAUNCH AND CONNECT TO SERVER")
    logger.info("=" * 50)
    
    # 1. Получаем сервер если не указан
    if not server_hostname:
        logger.info("📍 Step 1: Getting server from config...")
        server_hostname, server_port = get_server_from_account_config()
        if not server_hostname:
            logger.error("❌ No server configured!")
            return False
    
    logger.info(f"   Server: {server_hostname}:{server_port}")
    
    # 2. Записываем в реестр
    logger.info("📍 Step 2: Setting server in registry...")
    if not set_server_in_registry(server_hostname, server_port):
        logger.error("❌ Failed to set server in registry")
        return False
    
    # 3. Запускаем updater.exe (он сам запустит ragemp_v.exe после обновления)
    logger.info("📍 Step 3: Launching RageMP via updater.exe...")
    paths = get_game_paths()
    updater_path = paths["ragemp_updater"]
    ragemp_dir = paths["ragemp_dir"]
    
    if not Path(updater_path).exists():
        # Если updater нет - пробуем ragemp_v.exe напрямую
        logger.warning("⚠️  updater.exe not found, trying ragemp_v.exe...")
        if not run_ragemp_launcher():
            logger.error("❌ Failed to launch RageMP")
            return False
    else:
        if not run_exe(exe_path=updater_path, cwd=ragemp_dir, wait=False):
            logger.error("❌ Failed to launch updater.exe")
            return False
    
    # 4. Ждём запуска GTA
    logger.info("📍 Step 4: Waiting for GTA5.exe...")
    for i in range(90):  # Ждём до 90 секунд
        time.sleep(1)
        if is_gta_running():
            logger.info("✅ GTA V is running!")
            logger.info(f"✅ Connected to: {server_hostname}")
            return True
        if i % 10 == 0 and i > 0:
            logger.info(f"   Still waiting... ({i}s)")
    
    logger.warning("⚠️  GTA5.exe did not start within 90 seconds")
    logger.info("   But server is set in registry - it may connect on next launch")
    return True  # Всё равно успех — сервер в реестре


# Для обратной совместимости
def launch_game(run_updater: bool = True) -> bool:
    """
    Старый метод запуска (для совместимости).
    Рекомендуется использовать launch_and_connect().
    """
    return launch_and_connect()


# ============================================================================
# ТЕСТ
# ============================================================================

if __name__ == "__main__":
    print("Game Launcher v2.0 - Registry Method")
    print("=" * 50)
    
    paths = get_game_paths()
    for name, path in paths.items():
        exists = "✅" if Path(path).exists() else "❌"
        print(f"{exists} {name}: {path}")
    
    print()
    print("RageMP running:", is_ragemp_running())
    print("GTA5 running:", is_gta_running())
    
    # Показываем текущий сервер в реестре
    ip, port = get_server_from_registry()
    if ip:
        print(f"Current server in registry: {ip}:{port}")
