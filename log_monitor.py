"""
Log Monitor — отдельный демон для мониторинга логов бота.

Следит за файлом логов и отправляет важные события на сервер.
Запускай отдельно на время дебага:
    python log_monitor.py

Работает независимо от бота — даже если бот крашнется,
монитор отправит последние логи на сервер.
"""

import os
import sys
import time
import httpx
from pathlib import Path
from datetime import datetime
from config import LOGS_DIR, settings

# Уровни логов для отправки на сервер (все уровни для дебага)
SEND_LEVELS = ["DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL"]

# Сколько строк хранить в буфере при краше
CRASH_CONTEXT_LINES = 20


class LogMonitor:
    """Монитор логов с отправкой на сервер"""
    
    def __init__(self):
        self.api_url = settings.API_URL
        self.pc_name = os.environ.get("COMPUTERNAME", "unknown")
        self.last_position = 0
        self.last_lines = []  # Последние N строк для контекста
        self.current_log_file = None
        
        print(f"🔍 Log Monitor started")
        print(f"   API: {self.api_url}")
        print(f"   PC: {self.pc_name}")
        print(f"   Logs: {LOGS_DIR}")
        print("-" * 50)
    
    def get_today_log_file(self) -> Path:
        """Получить путь к сегодняшнему логу"""
        return LOGS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    
    def tail_file(self, filepath: Path) -> list:
        """Прочитать новые строки из файла"""
        if not filepath.exists():
            return []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                f.seek(self.last_position)
                new_lines = f.readlines()
                self.last_position = f.tell()
                return new_lines
        except Exception as e:
            print(f"⚠️ Error reading log: {e}")
            return []
    
    def parse_log_line(self, line: str) -> dict:
        """Распарсить строку лога"""
        line = line.strip()
        if not line:
            return None
        
        # Формат: 2025-12-26 14:30:00 | ERROR | message
        try:
            parts = line.split(" | ", 2)
            if len(parts) >= 3:
                return {
                    "timestamp": parts[0].strip(),
                    "level": parts[1].strip(),
                    "message": parts[2].strip()
                }
        except:
            pass
        
        return {"timestamp": "", "level": "INFO", "message": line}
    
    def is_crash_indicator(self, line: str) -> bool:
        """Проверить признаки краша"""
        crash_patterns = [
            "Traceback",
            "Exception:",
            "Error:",
            "CRITICAL",
            "Fatal error",
            "Process finished with exit code",
            "killed",
            "Segmentation fault",
        ]
        return any(p.lower() in line.lower() for p in crash_patterns)
    
    def send_to_server(self, level: str, message: str, extra: dict = None):
        """Отправить лог на сервер"""
        try:
            response = httpx.post(
                f"{self.api_url}/logs",
                json={
                    "machine_name": self.pc_name,
                    "level": level.lower(),
                    "message": message,
                    "extra": extra or {}
                },
                timeout=10
            )
            if response.status_code == 200:
                print(f"📤 Sent: [{level}] {message[:50]}...")
        except Exception as e:
            print(f"❌ Failed to send: {e}")
    
    def send_crash_report(self, crash_line: str):
        """Отправить отчёт о краше с контекстом"""
        context = "\n".join(self.last_lines[-CRASH_CONTEXT_LINES:])
        
        self.send_to_server(
            level="error",
            message=f"🔥 CRASH DETECTED: {crash_line[:200]}",
            extra={
                "context": context,
                "crash_line": crash_line,
                "pc_name": self.pc_name,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        print(f"\n{'='*50}")
        print("🔥 CRASH DETECTED!")
        print(f"{'='*50}")
        print(context)
        print(f"{'='*50}\n")
    
    def monitor(self, interval: float = 1.0):
        """Главный цикл мониторинга"""
        print(f"\n👀 Monitoring logs (interval: {interval}s)...")
        print("   Press Ctrl+C to stop\n")
        
        try:
            while True:
                log_file = self.get_today_log_file()
                
                # Проверяем смену дня
                if log_file != self.current_log_file:
                    self.current_log_file = log_file
                    self.last_position = 0
                    print(f"📁 Watching: {log_file}")
                
                # Читаем новые строки
                new_lines = self.tail_file(log_file)
                
                for line in new_lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Добавляем в буфер контекста
                    self.last_lines.append(line)
                    if len(self.last_lines) > CRASH_CONTEXT_LINES * 2:
                        self.last_lines = self.last_lines[-CRASH_CONTEXT_LINES:]
                    
                    # Парсим
                    parsed = self.parse_log_line(line)
                    if not parsed:
                        continue
                    
                    # Выводим в консоль
                    level = parsed["level"]
                    if level in ["ERROR", "CRITICAL"]:
                        print(f"🔴 {line}")
                    elif level == "WARN":
                        print(f"🟡 {line}")
                    
                    # Проверяем краш
                    if self.is_crash_indicator(line):
                        self.send_crash_report(line)
                    
                    # Отправляем важные логи
                    elif level in SEND_LEVELS:
                        self.send_to_server(level, parsed["message"])
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n👋 Monitor stopped")


def main():
    # Проверяем что мы в правильной директории
    if not LOGS_DIR.exists():
        print(f"❌ Logs directory not found: {LOGS_DIR}")
        print("   Make sure you're running from the client directory")
        sys.exit(1)
    
    monitor = LogMonitor()
    monitor.monitor(interval=1.0)


if __name__ == "__main__":
    main()
