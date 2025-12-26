import asyncio
import sys
import time
from config import settings
from core import VirtBot
from utils import setup_logger
from utils.ip_check import check_ip_access, IPStatus


async def main():
    """Точка входа"""
    logger = setup_logger()
    
    logger.info("=" * 50)
    logger.info(f"  VirtBot v{settings.VERSION}")
    logger.info(f"  Server: {settings.API_URL}")
    logger.info("=" * 50)
    
    # Проверка IP доступа
    logger.info("🔍 Checking IP access...")
    status, ip = check_ip_access()
    
    if status == IPStatus.NO_INTERNET:
        logger.warning("❌ NO INTERNET - Cannot get external IP")
        logger.info("🔄 TODO: Implement connection restore...")
        # TODO: Заглушка - попытка восстановить интернет
        logger.info("   Waiting 30 seconds before retry...")
        time.sleep(30)
        # Пока просто выходим, потом можно добавить retry логику
        sys.exit(1)
    
    logger.info(f"   Your IP: {ip}")
    
    if status == IPStatus.BLOCKED:
        logger.info("🛑 IP is in blocked list (home/office PC)")
        logger.info("   Farm loop will NOT start")
        logger.info("   Running in monitoring mode only...")
        # На домашних/офисных ПК — только heartbeat, без фарма
    else:
        logger.info("✅ IP allowed - Farm loop will start")
    
    logger.info("=" * 50)
    
    # Создаём бота с информацией о статусе IP
    bot = VirtBot()
    bot.ip_status = status  # Сохраняем статус для использования в bot.run()
    bot.external_ip = ip
    
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
