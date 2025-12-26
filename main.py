import asyncio
import sys
from config import settings
from core import VirtBot
from utils import setup_logger
from utils.ip_check import check_ip_access


async def main():
    """Точка входа"""
    logger = setup_logger()
    
    logger.info("=" * 50)
    logger.info(f"  VirtBot v{settings.VERSION}")
    logger.info(f"  Server: {settings.API_URL}")
    logger.info("=" * 50)
    
    # Проверка IP доступа
    logger.info("🔍 Checking IP access...")
    allowed, ip = check_ip_access()
    logger.info(f"   Your IP: {ip}")
    
    if not allowed:
        logger.error("❌ ACCESS DENIED - IP not in whitelist")
        logger.error("   Bot will not start on this IP")
        logger.info("=" * 50)
        sys.exit(0)
    
    logger.info("✅ IP access granted")
    logger.info("=" * 50)
    
    bot = VirtBot()
    
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
