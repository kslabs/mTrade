#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для проверки статуса mTrade сервера
"""

import os
import subprocess
import requests

PID_FILE = "mtrade_server.pid"

def check_process():
    """Проверить процесс по PID"""
    if not os.path.exists(PID_FILE):
        return None, False
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        result = subprocess.run(
            ['tasklist', '/FI', f'PID eq {pid}'],
            capture_output=True,
            text=True
        )
        
        is_running = str(pid) in result.stdout
        return pid, is_running
    except:
        return None, False

def check_web_server():
    """Проверить веб-сервер"""
    try:
        response = requests.get('http://localhost:5000/api/server/status', timeout=2)
        if response.status_code == 200:
            return True, response.json()
        return False, None
    except:
        return False, None

def main():
    print("📊 Статус mTrade сервера")
    print("=" * 60)
    
    # Проверяем процесс
    pid, process_running = check_process()
    
    if pid:
        print(f"PID файл: {PID_FILE}")
        print(f"PID: {pid}")
        print(f"Процесс: {'✅ Запущен' if process_running else '❌ Не найден'}")
    else:
        print("PID файл: ❌ Не найден")
        print("Процесс: ❌ Не запущен")
    
    print()
    
    # Проверяем веб-сервер
    web_running, status = check_web_server()
    
    if web_running:
        print("Веб-сервер: ✅ Доступен")
        print(f"Адрес: http://localhost:5000")
        
        if status:
            uptime_sec = status.get('uptime', 0)
            hours = int(uptime_sec // 3600)
            minutes = int((uptime_sec % 3600) // 60)
            print(f"Uptime: {hours}ч {minutes}мин")
    else:
        print("Веб-сервер: ❌ Недоступен")
    
    print("=" * 60)
    
    # Итоговый статус
    if process_running and web_running:
        print("\n✅ Сервер работает нормально")
    elif not process_running and not web_running:
        print("\n❌ Сервер не запущен")
        print("\nДля запуска используйте: python start.py")
    else:
        print("\n⚠️ Обнаружены проблемы")
        print("\nПопробуйте перезапустить: python restart.py")

if __name__ == '__main__':
    main()
