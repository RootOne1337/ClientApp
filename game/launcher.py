"""
Game Launcher Module

Handles:
- RAGE Multiplayer updater/launcher
- GTA V launch
- Process management

All paths are configurable and support different installations.
"""

import subprocess
import time
import os
from pathlib import Path
from typing import Optional

# Добавляем parent в path для импорта
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from utils import get_logger
    logger = get_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# ============================================================================
# КОНФИГУРАЦИЯ ПУТЕЙ (можно переопределить через data/paths.json)
# ============================================================================

DEFAULT_PATHS = {
    # RageMP
    "ragemp_dir": r"C:\Games\GTA5RP\RageMP",
    "ragemp_updater": r"C:\Games\GTA5RP\RageMP\updater.exe",
    "ragemp_launcher": r"C:\Games\GTA5RP\RageMP\ragemp_v.exe",
    
    # GTA V
    "gta_dir": r"C:\Games\GTA5RP\Grand Theft Auto V",
    "gta_exe": r"C:\Games\GTA5RP\Grand Theft Auto V\PlayGTAV.exe",
    
    # Rockstar
    "rockstar_launcher": r"C:\Program Files\Rockstar Games\Launcher\LauncherPatcher.exe",
}


def get_game_paths() -> dict:
    """Получить пути к игре (с возможностью переопределения через конфиг)"""
    # TODO: добавить загрузку из data/paths.json если нужно
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


def run_exe(exe_path: str, cwd: str = None, wait: bool = False, timeout: int = None) -> bool:
    """
    Запустить exe файл.
    
    Args:
        exe_path: Путь к exe
        cwd: Рабочая директория (важно для updater.exe!)
        wait: Ждать завершения процесса
        timeout: Таймаут ожидания (сек)
    
    Returns:
        True если успешно запущен/завершён
    """
    exe = Path(exe_path)
    
    if not exe.exists():
        logger.error(f"❌ File not found: {exe_path}")
        return False
    
    # Если cwd не указан, используем папку exe
    if cwd is None:
        cwd = str(exe.parent)
    
    logger.info(f"🚀 Running: {exe.name}")
    logger.info(f"   Path: {exe_path}")
    logger.info(f"   CWD: {cwd}")
    
    try:
        # Сохраняем текущую директорию
        original_cwd = os.getcwd()
        
        # Переходим в нужную директорию перед запуском
        os.chdir(cwd)
        
        if wait:
            # Запустить и ждать через subprocess (с shell=True для обхода elevation)
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
            # Запустить в фоне через os.startfile (нативный запуск Windows)
            os.startfile(str(exe))
            time.sleep(1)  # Даём время на запуск
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
# RAGE MULTIPLAYER
# ============================================================================

def run_ragemp_updater(wait_for_update: bool = True, timeout: int = 300) -> bool:
    """
    Запустить RAGE Multiplayer Updater.
    
    Важно: updater.exe должен запускаться из своей директории!
    
    Args:
        wait_for_update: Ждать завершения обновления
        timeout: Таймаут (сек)
    
    Returns:
        True если успешно
    """
    paths = get_game_paths()
    
    logger.info("=" * 50)
    logger.info("🔄 RageMP Updater")
    logger.info("=" * 50)
    
    updater_path = paths["ragemp_updater"]
    ragemp_dir = paths["ragemp_dir"]
    
    if not Path(updater_path).exists():
        logger.error(f"❌ Updater not found: {updater_path}")
        return False
    
    # Запускаем updater из его директории
    success = run_exe(
        exe_path=updater_path,
        cwd=ragemp_dir,  # Важно! updater должен работать из своей папки
        wait=wait_for_update,
        timeout=timeout
    )
    
    if success:
        logger.info("✅ RageMP update completed")
    else:
        logger.warning("⚠️  RageMP update may have failed or timed out")
    
    return success


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
        wait=False  # Не ждём, игра запускается
    )


def is_ragemp_running() -> bool:
    """Проверить запущен ли RageMP"""
    return is_process_running("ragemp_v.exe") or is_process_running("RAGEMP.exe")


def is_gta_running() -> bool:
    """Проверить запущена ли GTA V"""
    return is_process_running("GTA5.exe")


# ============================================================================
# ПОЛНЫЙ ЗАПУСК
# ============================================================================

def launch_game(run_updater: bool = True) -> bool:
    """
    Полный запуск игры.
    
    1. Запуск RageMP Updater (обновление)
    2. Запуск RageMP Launcher (игра)
    
    Args:
        run_updater: Запускать ли updater перед игрой
    
    Returns:
        True если игра запущена
    """
    logger.info("")
    logger.info("=" * 50)
    logger.info("🎮 LAUNCHING GAME")
    logger.info("=" * 50)
    
    # 1. Updater
    if run_updater:
        if not run_ragemp_updater(wait_for_update=True, timeout=300):
            logger.warning("Updater failed, trying to launch anyway...")
    
    # 2. Небольшая пауза
    time.sleep(2)
    
    # 3. Запуск игры
    if not run_ragemp_launcher():
        return False
    
    # 4. Ждём запуска GTA
    logger.info("⏳ Waiting for GTA5.exe to start...")
    for i in range(60):  # Ждём до 60 секунд
        time.sleep(1)
        if is_gta_running():
            logger.info("✅ GTA V is running!")
            return True
        if i % 10 == 0:
            logger.info(f"   Still waiting... ({i}s)")
    
    logger.warning("⚠️  GTA5.exe did not start within 60 seconds")
    return False


# ============================================================================
# ТЕСТ
# ============================================================================

if __name__ == "__main__":
    print("Game Launcher Test")
    print("=" * 50)
    
    paths = get_game_paths()
    for name, path in paths.items():
        exists = "✅" if Path(path).exists() else "❌"
        print(f"{exists} {name}: {path}")
    
    print()
    print("RageMP running:", is_ragemp_running())
    print("GTA5 running:", is_gta_running())
