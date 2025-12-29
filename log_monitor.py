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
    
    def __init__(self, send_existing: bool = True):
        self.api_url = settings.API_URL
        self.pc_name = os.environ.get("COMPUTERNAME", os.environ.get("HOSTNAME", "unknown"))
        self.last_position = 0
        self.last_lines = []  # Последние N строк для контекста
        self.current_log_file = None
        self.send_existing = send_existing
        self.sent_count = 0
        
        print(f"🔍 Log Monitor started")
        print(f"   API: {self.api_url}")
        print(f"   PC: {self.pc_name}")
        print(f"   Logs: {LOGS_DIR}")
        print(f"   Send existing logs: {send_existing}")
        print("-" * 50)
    
    def get_today_log_file(self) -> Path:
        """Получить путь к сегодняшнему логу"""
        return LOGS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    
    def read_file_lines(self, filepath: Path, from_position: int = 0) -> list:
        """Прочитать строки из файла начиная с позиции"""
        if not filepath.exists():
            return []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                f.seek(from_position)
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
                f"{self.api_url}/logs/",  # Добавил слэш в конце!
                json={
                    "machine_name": self.pc_name,
                    "level": level.lower(),
                    "message": message,
                    "extra": extra or {}
                },
                timeout=10
            )
            if response.status_code == 200:
                self.sent_count += 1
                # Показываем каждое 10-е сообщение чтобы не спамить
                if self.sent_count <= 5 or self.sent_count % 10 == 0:
                    print(f"📤 Sent #{self.sent_count}: [{level}] {message[:50]}...")
            else:
                print(f"❌ Server returned {response.status_code}: {response.text[:100]}")
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
    
    def process_line(self, line: str):
        """Обработать одну строку лога"""
        line = line.strip()
        if not line:
            return
        
        # Добавляем в буфер контекста
        self.last_lines.append(line)
        if len(self.last_lines) > CRASH_CONTEXT_LINES * 2:
            self.last_lines = self.last_lines[-CRASH_CONTEXT_LINES:]
        
        # Парсим
        parsed = self.parse_log_line(line)
        if not parsed:
            return
        
        level = parsed["level"]
        
        # Выводим ошибки в консоль
        if level in ["ERROR", "CRITICAL"]:
            print(f"🔴 {line}")
        elif level in ["WARN", "WARNING"]:
            print(f"🟡 {line}")
        
        # Проверяем краш
        if self.is_crash_indicator(line):
            self.send_crash_report(line)
        # Отправляем все логи
        elif level in SEND_LEVELS:
            self.send_to_server(level, parsed["message"])
    
    def monitor(self, interval: float = 1.0):
        """Главный цикл мониторинга"""
        print(f"\n👀 Monitoring logs (interval: {interval}s)...")
        print("   Press Ctrl+C to stop\n")
        
        try:
            while True:
                log_file = self.get_today_log_file()
                
                # Проверяем смену дня или первый запуск
                if log_file != self.current_log_file:
                    self.current_log_file = log_file
                    
                    if self.send_existing:
                        # Читаем ВСЕ существующие логи
                        self.last_position = 0
                        print(f"📁 Reading existing logs from: {log_file}")
                    else:
                        # Начинаем с конца файла
                        if log_file.exists():
                            self.last_position = log_file.stat().st_size
                        else:
                            self.last_position = 0
                        print(f"📁 Watching (new only): {log_file}")
                
                # Читаем новые строки
                new_lines = self.read_file_lines(log_file, self.last_position)
                
                if new_lines:
                    print(f"📝 Processing {len(new_lines)} lines...")
                else:
                    # Activity indicator (dot every 10 seconds of idle)
                    if int(time.time()) % 10 == 0:
                        print(".", end="", flush=True)
                
                for line in new_lines:
                    self.process_line(line)
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print(f"\n\n👋 Monitor stopped. Sent {self.sent_count} logs to server.")


def main():
    # Проверяем что мы в правильной директории
    if not LOGS_DIR.exists():
        print(f"❌ Logs directory not found: {LOGS_DIR}")
        print("   Make sure you're running from the client directory")
        sys.exit(1)
    
    # Аргументы командной строки (по умолчанию new-only)
    send_existing = "--all" in sys.argv
    
    print("=" * 50)
    print("  VirtBot Log Monitor")
    print("=" * 50)
    print()
    print("Usage:")
    print("  python log_monitor.py         # Only NEW logs (default)")
    print("  python log_monitor.py --all   # Send all existing + new logs")
    print()
    
    monitor = LogMonitor(send_existing=send_existing)
    monitor.monitor(interval=1.0)


if __name__ == "__main__":
    main()
