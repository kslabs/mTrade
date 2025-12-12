#!/usr/bin/env python

# -*- coding: utf-8 -*-

"""

Скрипт для перезапуска mTrade сервера

"""



import os

import sys

import subprocess
#!/usr/bin/env python

# -*- coding: utf-8 -*-

"""
Скрипт для перезапуска mTrade сервера
"""

import os
import sys
import subprocess
import time

PID_FILE = "mtrade_server.pid"


def _find_python_exec(script_dir):
    """Вернуть путь к python в .venv если есть, иначе sys.executable"""
    if os.name == 'nt':
        candidate = os.path.join(script_dir, '.venv', 'Scripts', 'python.exe')
    else:
        candidate = os.path.join(script_dir, '.venv', 'bin', 'python')
    if os.path.exists(candidate):
        return candidate
    return sys.executable


def stop_server():
    """Остановить сервер по PID-файлу"""
    if not os.path.exists(PID_FILE):
        print("⚠️ PID файл не найден — сервер, возможно, не запущен")
        return True

    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())

        print(f"🛑 Остановка текущего сервера (PID: {pid})...")

        if os.name == 'nt':
            result = subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True, text=True)
        else:
            result = subprocess.run(['kill', '-TERM', str(pid)], capture_output=True, text=True)

        time.sleep(1)

        if os.path.exists(PID_FILE):
            try:
                os.remove(PID_FILE)
            except Exception:
                pass

        if result.returncode == 0:
            print("✅ Процесс остановлен")
        else:
            print("⚠️ Процесс мог быть уже завершен или не найден")

        return True
    except Exception as e:
        print(f"⚠️ Ошибка при остановке: {e}")
        return False


def start_server():
    """Запустить сервер — предпочитаем python из .venv"""
    print("🚀 Запуск нового экземпляра сервера...")
    script_dir = os.path.abspath(os.path.dirname(__file__))
    python_exec = _find_python_exec(script_dir)
    print(f"Использую интерпретатор: {python_exec}")

    subprocess.Popen(
        [python_exec, os.path.join(script_dir, 'mTrade.py')],
        cwd=script_dir,
        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
    )

    # Подождём, чтобы mTrade мог записать PID
    time.sleep(2)

    if os.path.exists(PID_FILE):
        with open(PID_FILE, 'r') as f:
            new_pid = f.read().strip()
        print(f"✅ Сервер успешно запущен (PID: {new_pid})")
    else:
        print("⚠️ Сервер запущен, но PID не найден — проверьте логи mTrade")


def main():
    print("🔄 Перезапуск mTrade сервера...")
    print("=" * 60)

    if not stop_server():
        print("❌ Не удалось корректно остановить сервер — отмена перезапуска")
        return

    time.sleep(1)

    start_server()

    print("\n🌐 Адрес: http://localhost:5000")


if __name__ == '__main__':
    main()
    # Останавливаем

    stop_server()

    

    # Ждем немного

    time.sleep(1)

    

    # Запускаем

    start_server()

    

    print("\n🌐 Адрес: http://localhost:5000")



if __name__ == '__main__':

    main()

