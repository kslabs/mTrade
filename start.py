#!/usr/bin/env python

# -*- coding: utf-8 -*-

"""
Скрипт для запуска mTrade сервера
"""

#!/usr/bin/env python

# -*- coding: utf-8 -*-

"""
Скрипт для запуска mTrade сервера
"""

import os
import sys
import subprocess

PID_FILE = "mtrade_server.pid"


def is_running():
    """Проверить, запущен ли сервер (по PID-файлу)"""
    if not os.path.exists(PID_FILE):
        return False
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        # Windows: tasklist; POSIX: ps
        if os.name == 'nt':
            result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], capture_output=True, text=True)
            return str(pid) in result.stdout
        else:
            result = subprocess.run(['ps', '-p', str(pid)], capture_output=True, text=True)
            return str(pid) in result.stdout
    except Exception:
        return False


def main():
    if is_running():
        print("❌ Сервер уже запущен!")
        try:
            with open(PID_FILE, 'r') as f:
                pid = f.read().strip()
            print(f"   PID: {pid}")
        except Exception:
            pass
        print("\nИспользуйте:")
        print("  python stop.py     - для остановки")
        print("  python restart.py  - для перезапуска")
        return

    print("🚀 Запуск mTrade сервера...")
    print("=" * 60)

    # Определяем каталог приложения и выбираем интерпретатор (предпочитаем .venv)
    script_dir = os.path.abspath(os.path.dirname(__file__))

    venv_python = None
    if os.name == 'nt':
        candidate = os.path.join(script_dir, '.venv', 'Scripts', 'python.exe')
        if os.path.exists(candidate):
            venv_python = candidate
    else:
        candidate = os.path.join(script_dir, '.venv', 'bin', 'python')
        if os.path.exists(candidate):
            venv_python = candidate

    python_exec = venv_python if venv_python else sys.executable
    if venv_python:
        print(f"Использую интерпретатор виртуального окружения: {venv_python}")
    else:
        print(f"Использую системный интерпретатор: {sys.executable}")

    # Запускаем mTrade.py в новом окне/фоновом процессе
    try:
        creationflags = subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, 'CREATE_NEW_CONSOLE') else 0
        subprocess.Popen([python_exec, os.path.join(script_dir, "mTrade.py")], cwd=script_dir, creationflags=creationflags)
    except Exception as e:
        # Фоллбек: простое фоновое запус
        print(f"[START] Не удалось запустить в новом окне: {e}. Попытка фонового запуска.")
        subprocess.Popen([python_exec, os.path.join(script_dir, "mTrade.py")], cwd=script_dir)

    print("✅ Сервер запускается в отдельном окне...")
    print("🌐 Адрес: http://localhost:5000")
    print("\nУправление:")
    print("  python stop.py     - Остановить")
    print("  python restart.py  - Перезапустить")
    print("  python status.py   - Проверить статус")


if __name__ == '__main__':
    main()
import subprocess


