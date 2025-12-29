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
    """Press and release a key or key combo (e.g., CTRL+A, ALT+TAB)"""
    key = key.upper()
    
    # Check for key combo
    if '+' in key:
        parts = key.split('+')
        modifiers = []
        main_key = parts[-1]
        
        for mod in parts[:-1]:
            if mod in VK_CODES:
                modifiers.append(VK_CODES[mod])
        
        # Press modifiers
        for vk in modifiers:
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.02)
        
        # Press main key
        main_vk = VK_CODES.get(main_key, ord(main_key[0]) if main_key else 0)
        ctypes.windll.user32.keybd_event(main_vk, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(main_vk, 0, 2, 0)  # KEYUP
        
        # Release modifiers (reverse order)
        time.sleep(0.02)
        for vk in reversed(modifiers):
            ctypes.windll.user32.keybd_event(vk, 0, 2, 0)  # KEYUP
    else:
        # Single key
        vk = VK_CODES.get(key, ord(key[0]) if key else 0)
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


def switch_keyboard_layout(lang: str):
    """Switch keyboard layout to specified language using Windows API
    
    Args:
        lang: 'en' for English (US), 'ru' for Russian
    """
    layout_codes = {
        'en': '00000409',  # English US
        'ru': '00000419',  # Russian
    }
    
    layout_code = layout_codes.get(lang.lower())
    if not layout_code:
        logger.warning(f"Unknown keyboard layout: {lang}")
        return
    
    try:
        # Get foreground window
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        
        # Load layout
        hkl = ctypes.windll.user32.LoadKeyboardLayoutW(layout_code, 1)
        
        # Activate layout for current window
        # WM_INPUTLANGCHANGEREQUEST = 0x0050
        ctypes.windll.user32.PostMessageW(hwnd, 0x0050, 0, hkl)
        
        time.sleep(0.1)  # Wait for layout switch
        logger.debug(f"Switched to {lang.upper()} keyboard layout")
    except Exception as e:
        logger.warning(f"Failed to switch keyboard layout: {e}")


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
        
        # Cooldown tracking: script_name -> time when can trigger again
        self.cooldown_until: Dict[str, float] = {}
        self.default_cooldown = 60  # seconds between pixel triggers
        self.process_trigger_cooldown = 300  # 5 min for process triggers (game launch is slow)
        
        # Current script context for pixel name resolution in wait_for_pixel
        self._current_script_pixels = {}
        
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
                lang = action.get('lang')  # Optional: 'en' or 'ru'
                logger.debug(f"Type text: {text[:20]}..." + (f" (lang={lang})" if lang else ""))
                
                # Only switch layout if explicitly specified
                if lang:
                    switch_keyboard_layout(lang)
                
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
            
            elif action_type == 'wait_for_pixel':
                # Wait for pixel conditions with branching
                conditions = action.get('conditions', [])
                timeout_ms = action.get('timeout', 30000)
                check_interval_ms = action.get('check_interval', 500)
                on_timeout = action.get('on_timeout', 'exit')
                
                # Get pixels library from script's config via context
                # (passed implicitly through the action's parent script)
                pixels_library = self._current_script_pixels or {}
                
                logger.info(f"Waiting for pixel ({len(conditions)} conditions, timeout: {timeout_ms}ms)")
                
                start_time = time.time()
                timeout_sec = timeout_ms / 1000
                check_interval_sec = check_interval_ms / 1000
                
                while (time.time() - start_time) < timeout_sec:
                    # Check each condition
                    for condition in conditions:
                        cond_name = condition.get('name', 'unnamed')
                        
                        # New format: pixel_names, Old format: pixels array
                        pixel_names = condition.get('pixel_names', [])
                        inline_pixels = condition.get('pixels', [])
                        
                        # Resolve pixel_names to actual pixel data
                        if pixel_names:
                            pixels_to_check = []
                            for pn in pixel_names:
                                if pn in pixels_library:
                                    pixels_to_check.append(pixels_library[pn])
                        else:
                            pixels_to_check = inline_pixels
                        
                        if not pixels_to_check:
                            continue
                        
                        # AND logic: all pixels in condition must match
                        all_matched = True
                        for px in pixels_to_check:
                            x, y = px.get('x', 0), px.get('y', 0)
                            expected_color = px.get('color', '#FF0000')
                            tolerance = px.get('tolerance', 10)
                            
                            actual = get_pixel_color(x, y)
                            expected = hex_to_rgb(expected_color)
                            
                            if not color_match(actual, expected, tolerance):
                                all_matched = False
                                break
                        
                        if all_matched:
                            # Condition matched!
                            cond_action = condition.get('action', 'continue')
                            logger.info(f"Pixel condition matched: {cond_name} → {cond_action}")
                            
                            # Return special result for branching
                            return {'matched': cond_name, 'action': cond_action}
                    
                    time.sleep(check_interval_sec)
                
                # Timeout reached
                logger.warning(f"Pixel wait timeout after {timeout_ms}ms → {on_timeout}")
                return {'timeout': True, 'action': on_timeout}
            
            else:
                logger.warning(f"Unknown action type: {action_type}")
                return False
                
        except Exception as e:
            logger.error(f"Action {action_type} failed: {e}")
            return False
    
    def execute_script(self, script_name: str) -> bool:
        """Execute all actions in a script with branching support"""
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
        
        # Set pixels library context for wait_for_pixel action
        self._current_script_pixels = script.get('config', {}).get('pixels', {})
        
        logger.info(f"═══ SCRIPT START: {script_name} ({len(actions)} actions) ═══")
        
        # Use index-based loop for branching support
        i = 0
        while i < len(actions):
            action = actions[i]
            action_type = action.get('type', '?')
            
            # Build action description
            if action_type == 'click':
                desc = f"click({action.get('x')}, {action.get('y')})"
            elif action_type == 'key':
                desc = f"key({action.get('key')})"
            elif action_type == 'type':
                text = action.get('text', '')[:20] + ('...' if len(action.get('text', '')) > 20 else '')
                desc = f"type('{text}')"
            elif action_type == 'wait':
                desc = f"wait({action.get('ms')}ms)"
            elif action_type == 'cmd':
                cmd = action.get('command', '')[:30] + ('...' if len(action.get('command', '')) > 30 else '')
                desc = f"cmd('{cmd}')"
            elif action_type == 'call_command':
                desc = f"call_command({action.get('command')})"
            elif action_type == 'check_process':
                desc = f"check_process({action.get('process')})"
            elif action_type == 'wait_for_pixel':
                cond_count = len(action.get('conditions', []))
                timeout = action.get('timeout', 30000)
                desc = f"wait_for_pixel({cond_count} conditions, {timeout}ms)"
            else:
                desc = str(action)[:40]
            
            logger.info(f"  [{i+1}/{len(actions)}] {desc}")
            
            result = self.execute_action(action)
            
            # Handle branching results from wait_for_pixel
            if isinstance(result, dict):
                branch_action = result.get('action', 'continue')
                
                if branch_action == 'exit':
                    logger.info(f"═══ SCRIPT EXIT: {script_name} (branch action) ═══")
                    return True
                elif branch_action == 'continue':
                    i += 1
                    continue
                elif isinstance(branch_action, dict):
                    if 'goto' in branch_action:
                        goto_index = branch_action['goto']
                        logger.info(f"  → GOTO action {goto_index + 1}")
                        i = goto_index
                        continue
                    elif 'call' in branch_action:
                        call_script = branch_action['call']
                        logger.info(f"  → CALL script: {call_script}")
                        self.execute_script(call_script)
                        # After call, check if we should continue or exit
                        if branch_action.get('exit', False):
                            logger.info(f"═══ SCRIPT EXIT: {script_name} (after call) ═══")
                            return True
                        i += 1
                        continue
                else:
                    # Unknown branch action, continue
                    i += 1
                    continue
            
            # Normal result handling
            if not result:
                logger.error(f"═══ SCRIPT FAILED: {script_name} at action {i+1} ═══")
                return False
            
            i += 1
        
        logger.info(f"═══ SCRIPT DONE: {script_name} ═══")
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
                triggered = self.check_all_triggers()
                
                for script_name in triggered:
                    logger.info(f"Auto-executing triggered script: {script_name}")
                    self.execute_script(script_name)
                    time.sleep(1)  # Delay between scripts
                
            except Exception as e:
                logger.error(f"Scan loop error: {e}")
            
            time.sleep(self.scan_interval)
        
        logger.info("Trigger scanner stopped")
    
    def check_all_triggers(self) -> List[str]:
        """Check all trigger types: pixels and process_trigger"""
        triggered = []
        
        for name, script in self.scripts.items():
            if not script.get('enabled', True):
                continue
            
            # Check cooldown - skip if recently triggered
            if name in self.cooldown_until:
                if time.time() < self.cooldown_until[name]:
                    continue  # Still in cooldown
            
            config = script.get('config', {})
            # Custom cooldown or use defaults (process_trigger = 300s, pixel = 60s)
            custom_cooldown = config.get('cooldown')
            
            # Check process_triggers (new array format) with backward compatibility
            process_triggers = config.get('process_triggers', [])
            # Backward compatibility: convert old single format to array
            if not process_triggers and config.get('process_trigger', {}).get('process'):
                process_triggers = [config['process_trigger']]
            
            if process_triggers:
                # AND logic: all conditions must be true
                all_conditions_met = True
                trigger_descriptions = []
                
                for pt in process_triggers:
                    process_name = pt.get('process', '')
                    condition = pt.get('condition', 'running')
                    
                    if process_name:
                        is_running = is_process_running(process_name)
                        
                        if condition == 'not_running':
                            if is_running:
                                all_conditions_met = False
                                break
                            trigger_descriptions.append(f"{process_name}:OFF")
                        elif condition == 'running':
                            if not is_running:
                                all_conditions_met = False
                                break
                            trigger_descriptions.append(f"{process_name}:ON")
                
                if all_conditions_met and trigger_descriptions:
                    cooldown = custom_cooldown if custom_cooldown else self.process_trigger_cooldown
                    logger.info(f"Process triggers matched: [{', '.join(trigger_descriptions)}] → {name} (cooldown: {cooldown}s)")
                    triggered.append(name)
                    self.cooldown_until[name] = time.time() + cooldown
                    continue
            
            # Check trigger groups (use pixel_names references)
            # New format: trigger_groups = [{name: 'group1', pixel_names: ['pixel1', 'pixel2']}, ...]
            # Pixels library: pixels = {'pixel1': {x, y, color}, ...}
            trigger_groups = config.get('trigger_groups', [])
            pixels_library = config.get('pixels', {})
            
            # Backward compatibility: convert old pixel_groups to trigger_groups
            if not trigger_groups and config.get('pixel_groups'):
                trigger_groups = config['pixel_groups']  # old format with inline pixels
            
            if trigger_groups and is_process_running("GTA5.exe"):
                for group in trigger_groups:
                    group_name = group.get('name', 'group')
                    
                    # New format uses pixel_names, old format uses pixels array
                    pixel_names = group.get('pixel_names', [])
                    inline_pixels = group.get('pixels', [])
                    
                    # Resolve pixel_names to actual pixel data
                    if pixel_names:
                        pixels_to_check = []
                        for pn in pixel_names:
                            if pn in pixels_library:
                                pixels_to_check.append(pixels_library[pn])
                    else:
                        pixels_to_check = inline_pixels
                    
                    if not pixels_to_check:
                        continue
                    
                    # AND logic within group: ALL pixels in group must match
                    all_matched = True
                    for px in pixels_to_check:
                        x, y = px.get('x', 0), px.get('y', 0)
                        expected_color = px.get('color', '#FF0000')
                        tolerance = px.get('tolerance', 10)
                        
                        actual = get_pixel_color(x, y)
                        expected = hex_to_rgb(expected_color)
                        
                        if not color_match(actual, expected, tolerance):
                            all_matched = False
                            break
                    
                    # If all pixels in this group matched → trigger (OR between groups)
                    if all_matched:
                        cooldown = custom_cooldown if custom_cooldown else self.default_cooldown
                        logger.info(f"Trigger group matched: {name}.{group_name} ({len(pixels_to_check)} pixels) (cooldown: {cooldown}s)")
                        triggered.append(name)
                        self.cooldown_until[name] = time.time() + cooldown
                        break  # Stop checking other groups
        
        return triggered
    
    def run_startup_scripts(self):
        """Execute all scripts marked with run_on_startup: true"""
        logger.info("Running startup scripts...")
        
        for name, script in self.scripts.items():
            if not script.get('enabled', True):
                continue
            
            config = script.get('config', {})
            
            if config.get('run_on_startup', False):
                logger.info(f"Startup script: {name}")
                try:
                    self.execute_script(name)
                    
                    # Set cooldown to prevent immediate re-trigger by process_trigger
                    cooldown = config.get('cooldown', self.process_trigger_cooldown)
                    self.cooldown_until[name] = time.time() + cooldown
                    logger.info(f"Startup script {name} executed, cooldown: {cooldown}s")
                except Exception as e:
                    logger.error(f"Startup script {name} failed: {e}")
        
        logger.info("Startup scripts completed")
    
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
