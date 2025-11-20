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
        result = subprocess.run(
            ['tasklist', '/FI', f'PID eq {pid}'],
            capture_output=True,
            text=True
        )
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
        except:
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

    subprocess.Popen(
        [python_exec, os.path.join(script_dir, "mTrade.py")],
        cwd=script_dir,
        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
    )

    print("✅ Сервер запускается в отдельном окне...")
    print("🌐 Адрес: http://localhost:5000")
    print("\nУправление:")
    print("  python stop.py     - Остановить")
    print("  python restart.py  - Перезапустить")
    print("  python status.py   - Проверить статус")


if __name__ == '__main__':
    main()
#!/usr/bin/env python

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
    """Проверить, запущен ли сервер"""
    if not os.path.exists(PID_FILE):
        return False
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        result = subprocess.run(
            ['tasklist', '/FI', f'PID eq {pid}'],
            capture_output=True,
            text=True
        )
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
        except:
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

    subprocess.Popen(
        [python_exec, os.path.join(script_dir, "mTrade.py")],
        cwd=script_dir,
        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
    )

    print("✅ Сервер запускается в отдельном окне...")
    print("🌐 Адрес: http://localhost:5000")
    print("\nУправление:")
    print("  python stop.py     - Остановить")
    print("  python restart.py  - Перезапустить")
    print("  python status.py   - Проверить статус")


if __name__ == '__main__':
    main()
    )

    

    print("✅ Сервер запускается в отдельном окне...")

    print("🌐 Адрес: http://localhost:5000")

    print("\nУправление:")

    print("  python stop.py     - Остановить")

    print("  python restart.py  - Перезапустить")

    print("  python status.py   - Проверить статус")



if __name__ == '__main__':

    main()

