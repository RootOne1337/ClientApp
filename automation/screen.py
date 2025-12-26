import mss
import mss.tools
from datetime import datetime
from pathlib import Path
from config import SCREENSHOTS_DIR
from utils import get_logger


class ScreenCapture:
    """Захват экрана"""
    
    def __init__(self):
        self.logger = get_logger()
    
    def take_screenshot(self, filename: str = None) -> Path:
        """Сделать скриншот всего экрана"""
        if not filename:
            filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        filepath = SCREENSHOTS_DIR / filename
        
        with mss.mss() as sct:
            # Захват основного монитора
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(filepath))
        
        self.logger.info(f"📸 Screenshot saved: {filepath}")
        return filepath
    
    def take_region(self, x: int, y: int, width: int, height: int, filename: str = None) -> Path:
        """Сделать скриншот области"""
        if not filename:
            filename = f"region_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        filepath = SCREENSHOTS_DIR / filename
        
        with mss.mss() as sct:
            region = {"left": x, "top": y, "width": width, "height": height}
            screenshot = sct.grab(region)
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(filepath))
        
        return filepath
    
    def get_pixel_color(self, x: int, y: int) -> tuple:
        """Получить цвет пикселя (R, G, B)"""
        with mss.mss() as sct:
            region = {"left": x, "top": y, "width": 1, "height": 1}
            screenshot = sct.grab(region)
            # mss возвращает BGRA
            b, g, r = screenshot.pixel(0, 0)[:3]
            return (r, g, b)
