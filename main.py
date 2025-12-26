import asyncio
import sys
import time
from config import settings
from core import VirtBot
from utils import setup_logger
from utils.ip_check import check_ip_access, IPStatus
from utils.vpn_manager import (
    get_vpn_status, try_start_any_vpn, any_vpn_running, any_vpn_installed
)


# Константы для retry логики
IP_CHECK_RETRIES = 10
IP_CHECK_INTERVAL = 30  # секунд


def print_startup_banner(logger):
    """Вывести баннер при старте"""
    logger.info("=" * 50)
    logger.info(f"  VirtBot v{settings.VERSION}")
    logger.info(f"  Server: {settings.API_URL}")
    logger.info("=" * 50)


def check_ip_with_retries(logger, retries: int = IP_CHECK_RETRIES, interval: int = IP_CHECK_INTERVAL):
    """
    Проверить IP с повторными попытками.
    VPN может прогружаться, поэтому даём время.
    
    Returns:
        (status: IPStatus, ip: str, attempts: int)
    """
    for attempt in range(1, retries + 1):
        status, ip = check_ip_access()
        
        if status == IPStatus.ALLOWED:
            logger.info(f"✅ IP allowed on attempt {attempt}/{retries}: {ip}")
            return status, ip, attempt
        
        if status == IPStatus.NO_INTERNET:
            logger.warning(f"⚠️  No internet (attempt {attempt}/{retries})")
        else:  # BLOCKED
            logger.info(f"🔄 IP still blocked (attempt {attempt}/{retries}): {ip}")
        
        if attempt < retries:
            logger.info(f"   Waiting {interval} seconds...")
            time.sleep(interval)
    
    # Все попытки исчерпаны
    return status, ip, retries


def handle_blocked_ip(logger):
    """
    Обработка случая, когда IP заблокирован.
    Пытаемся запустить VPN и перепроверить IP.
    
    Returns:
        (final_status: IPStatus, ip: str, can_start_farm: bool)
    """
    logger.info("")
    logger.info("=" * 50)
    logger.info("🔍 IP заблокирован. Проверяем VPN...")
    logger.info("=" * 50)
    
    # Получаем статус VPN
    vpn_status = get_vpn_status()
    for vpn_name, info in vpn_status.items():
        status_str = []
        if info["installed"]:
            status_str.append("installed")
        if info["running"]:
            status_str.append("running")
        logger.info(f"   {vpn_name}: {', '.join(status_str) if status_str else 'not found'}")
    
    # Если VPN уже запущен — проверяем IP снова (может ещё не подключился)
    if any_vpn_running():
        logger.info("")
        logger.info("🔄 VPN уже запущен. Ждём подключения...")
        status, ip, attempts = check_ip_with_retries(logger)
        
        if status == IPStatus.ALLOWED:
            return status, ip, True
        else:
            logger.warning("⚠️  VPN запущен, но IP всё ещё заблокирован")
            logger.info("   Ожидаем команд от оператора...")
            return status, ip, False
    
    # Если VPN не запущен, но установлен — пытаемся запустить
    if any_vpn_installed():
        logger.info("")
        logger.info("🚀 Пытаемся запустить VPN...")
        
        started, vpn_names = try_start_any_vpn()
        if started:
            logger.info(f"✅ Запущено: {', '.join(vpn_names)}")
            logger.info("")
            logger.info("🔄 Ждём подключения VPN...")
            
            # Даём VPN время на подключение и проверяем IP
            time.sleep(5)  # Небольшая пауза для инициализации
            status, ip, attempts = check_ip_with_retries(logger)
            
            if status == IPStatus.ALLOWED:
                return status, ip, True
            else:
                logger.warning("⚠️  VPN запущен, но IP всё ещё заблокирован")
                logger.info("   Возможно проблема с VPN подключением")
                logger.info("   Ожидаем команд от оператора...")
                return status, ip, False
        else:
            logger.warning("⚠️  Не удалось запустить VPN")
    else:
        logger.warning("⚠️  VPN не установлен")
    
    # VPN нет или не удалось запустить
    logger.info("")
    logger.info("🛑 Не удалось получить разрешённый IP")
    logger.info("   Ожидаем команд от оператора...")
    
    status, ip = check_ip_access()
    return status, ip, False


def handle_no_internet(logger):
    """
    Обработка случая, когда нет интернета.
    """
    logger.warning("")
    logger.warning("=" * 50)
    logger.warning("❌ НЕТ ИНТЕРНЕТА")
    logger.warning("=" * 50)
    logger.warning("   Проверьте подключение")
    logger.warning("   Ожидаем команд от оператора...")
    
    return IPStatus.NO_INTERNET, "", False


async def main():
    """Точка входа"""
    logger = setup_logger()
    
    print_startup_banner(logger)
    
    # ==================== ПРОВЕРКА IP ====================
    logger.info("")
    logger.info("🔍 Checking IP access...")
    
    # Первая проверка IP (с retry на случай если VPN ещё грузится)
    status, ip, attempts = check_ip_with_retries(logger)
    
    can_start_farm = False
    
    if status == IPStatus.ALLOWED:
        logger.info(f"✅ IP разрешён: {ip}")
        can_start_farm = True
        
    elif status == IPStatus.BLOCKED:
        logger.info(f"🛑 IP заблокирован: {ip}")
        status, ip, can_start_farm = handle_blocked_ip(logger)
        
    elif status == IPStatus.NO_INTERNET:
        status, ip, can_start_farm = handle_no_internet(logger)
    
    # ==================== ИТОГ ====================
    logger.info("")
    logger.info("=" * 50)
    if can_start_farm:
        logger.info("✅ Готов к работе! Фарм будет запущен.")
    else:
        logger.info("🛑 Режим ожидания. Фарм НЕ запущен.")
        logger.info("   Бот слушает команды от сервера.")
    logger.info("=" * 50)
    logger.info("")
    
    # ==================== ЗАПУСК БОТА ====================
    bot = VirtBot()
    bot.ip_status = status
    bot.external_ip = ip
    bot.can_farm = can_start_farm  # Новый флаг для game loop
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        bot.stop()
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
