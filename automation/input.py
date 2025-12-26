import time
from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Button, Controller as MouseController
from utils import get_logger


class InputEmulator:
    """Эмуляция ввода клавиатуры и мыши"""
    
    def __init__(self):
        self.keyboard = KeyboardController()
        self.mouse = MouseController()
        self.logger = get_logger()
    
    def press_key(self, key, duration: float = 0.1):
        """Нажать клавишу"""
        self.keyboard.press(key)
        time.sleep(duration)
        self.keyboard.release(key)
    
    def press_keys(self, *keys, duration: float = 0.1):
        """Нажать несколько клавиш одновременно (например Ctrl+V)"""
        for key in keys:
            self.keyboard.press(key)
        time.sleep(duration)
        for key in reversed(keys):
            self.keyboard.release(key)
    
    def type_text(self, text: str, delay: float = 0.03):
        """Набрать текст"""
        for char in text:
            self.keyboard.type(char)
            time.sleep(delay)
    
    def move_mouse(self, x: int, y: int):
        """Переместить мышь"""
        self.mouse.position = (x, y)
    
    def click(self, x: int = None, y: int = None, button: str = "left", count: int = 1):
        """Клик мышью"""
        if x is not None and y is not None:
            self.mouse.position = (x, y)
            time.sleep(0.05)
        
        btn = Button.left if button == "left" else Button.right
        self.mouse.click(btn, count)
    
    def scroll(self, dx: int = 0, dy: int = 0):
        """Прокрутка"""
        self.mouse.scroll(dx, dy)
    
    # ==================== GTA-специфичные действия ====================
    
    def open_chat(self):
        """Открыть чат GTA"""
        self.press_key('t')
        time.sleep(0.2)
    
    def send_chat(self, message: str):
        """Отправить сообщение в чат GTA"""
        self.open_chat()
        self.type_text(message)
        self.press_key(Key.enter)
    
    def press_enter(self):
        """Нажать Enter"""
        self.press_key(Key.enter)
    
    def press_escape(self):
        """Нажать Escape"""
        self.press_key(Key.esc)
    
    def press_f_key(self, num: int):
        """Нажать F1-F12"""
        key = getattr(Key, f"f{num}", None)
        if key:
            self.press_key(key)
