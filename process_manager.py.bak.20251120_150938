"""
Менеджер управления процессом сервера Gate.io Multi-Trading
Управление PID файлом, проверка состояния, завершение процесса
"""

import os
import sys
import signal
import atexit


class ProcessManager:
    """Менеджер для управления процессом сервера"""
    
    PID_FILE = "mtrade_server.pid"
    
    @staticmethod
    def write_pid():
        """Записать PID текущего процесса"""
        pid = os.getpid()
        with open(ProcessManager.PID_FILE, 'w') as f:
            f.write(str(pid))
        print(f"[PID] Процесс запущен с PID: {pid}")
        
    @staticmethod
    def read_pid():
        """Прочитать PID из файла"""
        if os.path.exists(ProcessManager.PID_FILE):
            try:
                with open(ProcessManager.PID_FILE, 'r') as f:
                    return int(f.read().strip())
            except:
                return None
        return None
    
    @staticmethod
    def remove_pid():
        """Удалить PID файл"""
        if os.path.exists(ProcessManager.PID_FILE):
            os.remove(ProcessManager.PID_FILE)
            print("[PID] PID файл удален")
    
    @staticmethod
    def is_running():
        """Проверить, запущен ли процесс"""
        pid = ProcessManager.read_pid()
        if pid is None:
            return False
        
        # Проверяем, существует ли процесс
        try:
            # На Windows используем tasklist
            import subprocess
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}'],
                capture_output=True,
                text=True
            )
            return str(pid) in result.stdout
        except:
            return False
    
    @staticmethod
    def kill_process(pid=None):
        """Убить процесс по PID"""
        if pid is None:
            pid = ProcessManager.read_pid()
        
        if pid is None:
            print("[PID] PID не найден")
            return False
        
        try:
            import subprocess
            # На Windows используем taskkill
            subprocess.run(['taskkill', '/F', '/PID', str(pid)], check=True)
            print(f"[PID] Процесс {pid} завершен")
            ProcessManager.remove_pid()
            return True
        except Exception as e:
            print(f"[PID] Ошибка при завершении процесса: {e}")
            return False
    
    @staticmethod
    def setup_cleanup():
        """Настроить автоматическую очистку при выходе"""
        atexit.register(ProcessManager.remove_pid)
        
        # Обработчики сигналов для graceful shutdown
        def signal_handler(signum, frame):
            print("\n[SHUTDOWN] Получен сигнал завершения...")
            ProcessManager.remove_pid()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
