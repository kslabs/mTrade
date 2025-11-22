#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для остановки mTrade сервера
"""

import os
import subprocess
import time

PID_FILE = "mtrade_server.pid"

def main():
    if not os.path.exists(PID_FILE):
        print("❌ Сервер не запущен (PID файл не найден)")
        return
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        print(f"🛑 Остановка mTrade сервера (PID: {pid})...")
        
        # Убиваем процесс
        result = subprocess.run(
            ['taskkill', '/F', '/PID', str(pid)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Сервер успешно остановлен")
            
            # Удаляем PID файл
            time.sleep(0.5)
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
        else:
            print("⚠️ Процесс не найден или уже завершен")
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
    
    except Exception as e:
        print(f"❌ Ошибка при остановке: {e}")

if __name__ == '__main__':
    main()
