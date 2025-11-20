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

        

        # Проверяем процесс

        result = subprocess.run(

            ['tasklist', '/FI', f'PID eq {pid}'],

            capture_output=True,

            text=True

        )

        return str(pid) in result.stdout

    except:

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

    

    # Определяем каталог приложения и запускаем сервер из него
    script_dir = os.path.abspath(os.path.dirname(__file__))

    subprocess.Popen(
        [sys.executable, os.path.join(script_dir, "mTrade.py")],
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

