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



def stop_server():

    """Остановить сервер"""
    script_dir = os.path.abspath(os.path.dirname(__file__))

    subprocess.Popen(
        [sys.executable, os.path.join(script_dir, "mTrade.py")],
        cwd=script_dir,
        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
    )

        with open(PID_FILE, 'r') as f:

            pid = int(f.read().strip())

        

        print(f"🛑 Остановка текущего сервера (PID: {pid})...")

        subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True)

        

        time.sleep(1)

        

        if os.path.exists(PID_FILE):

            os.remove(PID_FILE)

        

        return True

    except Exception as e:

        print(f"⚠️ Ошибка при остановке: {e}")

        return False



def start_server():

    """Запустить сервер"""

    print("🚀 Запуск нового экземпляра сервера...")

    

    subprocess.Popen(

        [sys.executable, "mTrade.py"],

        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0

    )

    

    time.sleep(2)

    

    if os.path.exists(PID_FILE):

        with open(PID_FILE, 'r') as f:

            new_pid = f.read().strip()

        print(f"✅ Сервер успешно перезапущен (новый PID: {new_pid})")

    else:

        print("⚠️ Сервер запущен, но PID не найден")



def main():

    print("🔄 Перезапуск mTrade сервера...")

    print("=" * 60)

    

    # Останавливаем

    stop_server()

    

    # Ждем немного

    time.sleep(1)

    

    # Запускаем

    start_server()

    

    print("\n🌐 Адрес: http://localhost:5000")



if __name__ == '__main__':

    main()

