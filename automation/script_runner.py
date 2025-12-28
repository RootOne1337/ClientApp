"""
ScriptRunner - Dynamic automation scripts executor

Features:
- Fetches scripts from server API
- Caches locally for offline work
- Scans triggers every 5 seconds (only if game running)
- Executes actions: click, key, type, wait, cmd, check_process
- Variable substitution from account.json ({{email}}, {{password}}, etc.)
"""

import os
import sys
import json
import time
import ctypes
import subprocess
import threading
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

# Setup logging
logger = logging.getLogger(__name__)


# ============================================================================
# INPUT HELPERS (Windows API)
# ============================================================================

# Virtual key codes
VK_CODES = {
    'ESC': 0x1B, 'ENTER': 0x0D, 'SPACE': 0x20, 'TAB': 0x09,
    'BACKSPACE': 0x08, 'DELETE': 0x2E, 'INSERT': 0x2D,
    'UP': 0x26, 'DOWN': 0x28, 'LEFT': 0x25, 'RIGHT': 0x27,
    'HOME': 0x24, 'END': 0x23, 'PAGEUP': 0x21, 'PAGEDOWN': 0x22,
    'F1': 0x70, 'F2': 0x71, 'F3': 0x72, 'F4': 0x73, 'F5': 0x74,
    'F6': 0x75, 'F7': 0x76, 'F8': 0x77, 'F9': 0x78, 'F10': 0x79,
    'F11': 0x7A, 'F12': 0x7B,
    'SHIFT': 0x10, 'CTRL': 0x11, 'ALT': 0x12,
    '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
    '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
    'A': 0x41, 'B': 0x42, 'C': 0x43, 'D': 0x44, 'E': 0x45,
    'F': 0x46, 'G': 0x47, 'H': 0x48, 'I': 0x49, 'J': 0x4A,
    'K': 0x4B, 'L': 0x4C, 'M': 0x4D, 'N': 0x4E, 'O': 0x4F,
    'P': 0x50, 'Q': 0x51, 'R': 0x52, 'S': 0x53, 'T': 0x54,
    'U': 0x55, 'V': 0x56, 'W': 0x57, 'X': 0x58, 'Y': 0x59, 'Z': 0x5A,
}


def click(x: int, y: int, delay_ms: int = 50):
    """Click at screen position"""
    ctypes.windll.user32.SetCursorPos(x, y)
    time.sleep(delay_ms / 1000)
    ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)  # LEFTDOWN
    time.sleep(0.05)
    ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)  # LEFTUP


def press_key(key: str):
    """Press and release a key"""
    vk = VK_CODES.get(key.upper(), ord(key.upper()[0]) if key else 0)
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(vk, 0, 2, 0)  # KEYUP


def type_text(text: str, delay_ms: int = 30):
    """Type text character by character"""
    for char in text:
        # Use SendInput for Unicode support
        if char.isalnum() or char in ' !@#$%^&*()_+-=[]{}|;:\'",.<>?/\\`~':
            vk = VK_CODES.get(char.upper(), ord(char.upper()))
            
            # Check if shift needed
            needs_shift = char.isupper() or char in '!@#$%^&*()_+{}|:"<>?~'
            
            if needs_shift:
                ctypes.windll.user32.keybd_event(0x10, 0, 0, 0)  # SHIFT down
            
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.02)
            ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
            
            if needs_shift:
                ctypes.windll.user32.keybd_event(0x10, 0, 2, 0)  # SHIFT up
        
        time.sleep(delay_ms / 1000)


def get_pixel_color(x: int, y: int) -> tuple:
    """Get RGB color of pixel at screen position"""
    hdc = ctypes.windll.user32.GetDC(0)
    color = ctypes.windll.gdi32.GetPixel(hdc, x, y)
    ctypes.windll.user32.ReleaseDC(0, hdc)
    
    if color == -1:
        return (0, 0, 0)
    
    r = color & 0xFF
    g = (color >> 8) & 0xFF
    b = (color >> 16) & 0xFF
    return (r, g, b)


def hex_to_rgb(hex_color: str) -> tuple:
    """Convert #RRGGBB to (R, G, B)"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def color_match(actual: tuple, expected: tuple, tolerance: int = 10) -> bool:
    """Check if colors match within tolerance"""
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected))


def is_process_running(process_name: str) -> bool:
    """Check if process is running"""
    try:
        output = subprocess.check_output(
            f'tasklist /FI "IMAGENAME eq {process_name}" /NH',
            shell=True, stderr=subprocess.DEVNULL
        ).decode('cp866', errors='ignore')
        return process_name.lower() in output.lower()
    except:
        return False


# ============================================================================
# SCRIPT RUNNER
# ============================================================================

class ScriptRunner:
    """
    Manages and executes automation scripts.
    
    - Syncs scripts from server
    - Caches locally
    - Scans triggers periodically
    - Executes actions
    """
    
    def __init__(self, data_dir: Path, api_url: str = None):
        self.data_dir = Path(data_dir)
        self.scripts_dir = self.data_dir / "scripts"
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        
        self.api_url = api_url
        self.scripts: Dict[str, dict] = {}
        self.account_config: dict = {}
        self.running = False
        self.scan_thread: Optional[threading.Thread] = None
        self.scan_interval = 5  # seconds
        
        # Callback for call_command action (set by Bot)
        self.command_callback = None
        
        # Load account config for variables
        self._load_account_config()
        
        # Load cached scripts
        self._load_cached_scripts()
    
    def set_command_callback(self, callback):
        """Set callback function for call_command action. Callback should accept (command_name, params) and return result."""
        self.command_callback = callback
    
    def _load_account_config(self):
        """Load account.json for variable substitution"""
        account_file = self.data_dir / "account.json"
        if account_file.exists():
            try:
                with open(account_file, 'r', encoding='utf-8') as f:
                    self.account_config = json.load(f)
                logger.info(f"Loaded account config with {len(self.account_config)} fields")
            except Exception as e:
                logger.error(f"Failed to load account.json: {e}")
    
    def _load_cached_scripts(self):
        """Load scripts from local cache"""
        for script_file in self.scripts_dir.glob("*.json"):
            try:
                with open(script_file, 'r', encoding='utf-8') as f:
                    script = json.load(f)
                    if script.get('enabled', True):
                        self.scripts[script['name']] = script
                        logger.debug(f"Loaded script: {script['name']}")
            except Exception as e:
                logger.error(f"Failed to load {script_file}: {e}")
        
        logger.info(f"Loaded {len(self.scripts)} cached scripts")
    
    def sync_from_server(self) -> bool:
        """Fetch scripts from API and cache locally"""
        if not self.api_url:
            logger.warning("No API URL configured, using cached scripts only")
            return False
        
        try:
            import requests
            response = requests.get(f"{self.api_url}/scripts/", timeout=10)
            response.raise_for_status()
            
            scripts = response.json()
            
            # Save each script to cache
            for script in scripts:
                script_file = self.scripts_dir / f"{script['name']}.json"
                with open(script_file, 'w', encoding='utf-8') as f:
                    json.dump(script, f, indent=2, ensure_ascii=False)
                
                if script.get('enabled', True):
                    self.scripts[script['name']] = script
            
            logger.info(f"Synced {len(scripts)} scripts from server")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync scripts: {e}")
            return False
    
    def substitute_variables(self, text: str) -> str:
        """Replace {{variable}} with values from account.json"""
        if not text or '{{' not in text:
            return text
        
        result = text
        for key, value in self.account_config.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        
        return result
    
    def execute_action(self, action: dict) -> bool:
        """Execute a single action"""
        action_type = action.get('type', '')
        
        try:
            if action_type == 'click':
                x, y = action.get('x', 0), action.get('y', 0)
                logger.debug(f"Click at ({x}, {y})")
                click(x, y)
                return True
            
            elif action_type == 'key':
                key = action.get('key', '')
                logger.debug(f"Press key: {key}")
                press_key(key)
                return True
            
            elif action_type == 'type':
                text = self.substitute_variables(action.get('text', ''))
                logger.debug(f"Type text: {text[:20]}...")
                type_text(text)
                return True
            
            elif action_type == 'wait':
                ms = action.get('ms', 1000)
                logger.debug(f"Wait {ms}ms")
                time.sleep(ms / 1000)
                return True
            
            elif action_type == 'cmd':
                command = self.substitute_variables(action.get('command', ''))
                logger.debug(f"Run command: {command}")
                subprocess.Popen(command, shell=True, 
                               creationflags=subprocess.CREATE_NO_WINDOW)
                return True
            
            elif action_type == 'check_process':
                process = action.get('process', '')
                logger.debug(f"Check process: {process}")
                # Wait until process is running (max 60 sec)
                for _ in range(12):
                    if is_process_running(process):
                        logger.info(f"Process {process} is running")
                        return True
                    time.sleep(5)
                logger.warning(f"Process {process} not found after 60s")
                return False
            
            elif action_type == 'call_command':
                command_name = action.get('command', '')
                params = action.get('params', {})
                logger.debug(f"Call command: {command_name}")
                
                if self.command_callback:
                    try:
                        result = self.command_callback(command_name, params)
                        logger.info(f"Command {command_name} returned: {result}")
                        return True
                    except Exception as e:
                        logger.error(f"Command {command_name} failed: {e}")
                        return False
                else:
                    logger.warning("No command callback set, cannot execute call_command")
                    return False
            
            else:
                logger.warning(f"Unknown action type: {action_type}")
                return False
                
        except Exception as e:
            logger.error(f"Action {action_type} failed: {e}")
            return False
    
    def execute_script(self, script_name: str) -> bool:
        """Execute all actions in a script"""
        script = self.scripts.get(script_name)
        if not script:
            logger.error(f"Script not found: {script_name}")
            return False
        
        if not script.get('enabled', True):
            logger.warning(f"Script {script_name} is disabled")
            return False
        
        actions = script.get('config', {}).get('actions', [])
        if not actions:
            logger.warning(f"Script {script_name} has no actions")
            return False
        
        logger.info(f"Executing script: {script_name} ({len(actions)} actions)")
        
        for i, action in enumerate(actions):
            logger.debug(f"  Action {i+1}/{len(actions)}: {action.get('type')}")
            if not self.execute_action(action):
                logger.error(f"Script {script_name} stopped at action {i+1}")
                return False
        
        logger.info(f"Script {script_name} completed successfully")
        return True
    
    def check_triggers(self) -> List[str]:
        """Check all pixel triggers, return list of triggered script names"""
        triggered = []
        
        for name, script in self.scripts.items():
            if not script.get('enabled', True):
                continue
            
            config = script.get('config', {})
            pixels = config.get('pixels', {})
            
            if not pixels:
                continue  # No triggers, manual only
            
            # Check each pixel trigger
            for trigger_name, pixel in pixels.items():
                x, y = pixel.get('x', 0), pixel.get('y', 0)
                expected_color = pixel.get('color', '#FF0000')
                tolerance = pixel.get('tolerance', 10)
                
                actual = get_pixel_color(x, y)
                expected = hex_to_rgb(expected_color)
                
                if color_match(actual, expected, tolerance):
                    logger.info(f"Trigger matched: {name}.{trigger_name} at ({x},{y})")
                    triggered.append(name)
                    break  # One trigger per script is enough
        
        return triggered
    
    def _scan_loop(self):
        """Background thread: periodically check triggers"""
        logger.info(f"Trigger scanner started (interval: {self.scan_interval}s)")
        
        while self.running:
            try:
                # Only scan if GTA5 is running
                if not is_process_running("GTA5.exe"):
                    time.sleep(self.scan_interval)
                    continue
                
                triggered = self.check_triggers()
                
                for script_name in triggered:
                    logger.info(f"Auto-executing triggered script: {script_name}")
                    self.execute_script(script_name)
                    time.sleep(1)  # Delay between scripts
                
            except Exception as e:
                logger.error(f"Scan loop error: {e}")
            
            time.sleep(self.scan_interval)
        
        logger.info("Trigger scanner stopped")
    
    def start(self):
        """Start the trigger scanner"""
        if self.running:
            return
        
        self.running = True
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()
        logger.info("ScriptRunner started")
    
    def stop(self):
        """Stop the trigger scanner"""
        self.running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=2)
        logger.info("ScriptRunner stopped")
    
    def get_scripts_list(self) -> List[str]:
        """Get list of available script names"""
        return list(self.scripts.keys())


# ============================================================================
# STANDALONE TEST
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # Test
    runner = ScriptRunner(Path("data"))
    print(f"Scripts loaded: {runner.get_scripts_list()}")
    
    # Test pixel color
    x, y = 100, 100
    print(f"Pixel at ({x}, {y}): {get_pixel_color(x, y)}")
