#!/usr/bin/env python3
"""
КРИТИЧЕСКИЙ ПЕРЕЗАПУСК СЕРВЕРА
Останавливает старый процесс и запускает новый с исправленным кодом
"""
import os
import sys
import time
import psutil
import subprocess
from pathlib import Path

def find_mtrade_processes():
    """Найти все процессы mTrade"""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline')
            if cmdline and any('mTrade.py' in str(arg) for arg in cmdline):
                processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return processes

def stop_mtrade():
    """Остановить все процессы mTrade"""
    processes = find_mtrade_processes()
    
    if not processes:
        print("✓ Процессы mTrade не найдены")
        return True
    
    print(f"Найдено процессов mTrade: {len(processes)}")
    
    for proc in processes:
        try:
            print(f"  Остановка процесса PID={proc.pid}...")
            proc.terminate()
        except Exception as e:
            print(f"  ⚠️ Ошибка при остановке PID={proc.pid}: {e}")
    
    # Ждём завершения
    print("  Ожидание завершения процессов (5 секунд)...")
    time.sleep(5)
    
    # Проверяем, завершились ли
    remaining = find_mtrade_processes()
    if remaining:
        print(f"  ⚠️ Осталось {len(remaining)} процессов, принудительное завершение...")
        for proc in remaining:
            try:
                proc.kill()
            except Exception:
                pass
        time.sleep(2)
    
    final_check = find_mtrade_processes()
    if final_check:
        print(f"  ❌ Не удалось остановить {len(final_check)} процессов!")
        for proc in final_check:
            print(f"     PID={proc.pid}")
        return False
    
    print("  ✓ Все процессы остановлены")
    return True

def start_mtrade():
    """Запустить mTrade с новым кодом"""
    script_path = Path(__file__).parent / 'mTrade.py'
    
    if not script_path.exists():
        print(f"❌ Файл {script_path} не найден!")
        return False
    
    print(f"\n🚀 Запуск mTrade с исправленным кодом...")
    print(f"   Файл: {script_path}")
    
    try:
        # Запускаем в новом окне
        if sys.platform == 'win32':
            subprocess.Popen(
                ['python', str(script_path)],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            subprocess.Popen(['python', str(script_path)])
        
        print("   ✓ Сервер запущен")
        print("\n" + "="*80)
        print("ПРОВЕРЬТЕ ЛОГИ СЕРВЕРА!")
        print("="*80)
        print("Ищите сообщения:")
        print("  [LOCK_INIT][XXX] Создан новый Lock для валюты")
        print("  [PROTECTION][XXX] ... УСТАНОВЛЕН И СОХРАНЁН")
        print("\nЕсли этих сообщений нет - сообщите об этом!")
        print("="*80)
        return True
    except Exception as e:
        print(f"   ❌ Ошибка при запуске: {e}")
        return False

def main():
    print("="*80)
    print("КРИТИЧЕСКИЙ ПЕРЕЗАПУСК СЕРВЕРА")
    print("="*80)
    print()
    print("⚠️ ВНИМАНИЕ: Сервер будет остановлен и перезапущен!")
    print()
    
    response = input("Продолжить? (yes/no): ")
    if response.lower() not in ['yes', 'y', 'да', 'д']:
        print("Отменено")
        return
    
    print("\n" + "="*80)
    print("ШАГ 1: ОСТАНОВКА СТАРОГО СЕРВЕРА")
    print("="*80)
    
    if not stop_mtrade():
        print("\n❌ Не удалось остановить сервер!")
        print("Остановите вручную и запустите: python mTrade.py")
        return
    
    print("\n" + "="*80)
    print("ШАГ 2: ПРОВЕРКА ИСПРАВЛЕНИЙ В КОДЕ")
    print("="*80)
    
    # Проверяем, что исправления на месте
    autotrader_path = Path(__file__).parent / 'autotrader.py'
    if not autotrader_path.exists():
        print("❌ Файл autotrader.py не найден!")
        return
    
    with open(autotrader_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    checks = {
        'Мастер-Lock в __init__': '_locks_creation_lock = Lock()' in code,
        'Использование with _locks_creation_lock': 'with self._locks_creation_lock:' in code,
        'Логирование [LOCK_INIT]': '[LOCK_INIT]' in code,
    }
    
    all_ok = True
    for check_name, result in checks.items():
        status = "✅" if result else "❌"
        print(f"  {status} {check_name}")
        if not result:
            all_ok = False
    
    if not all_ok:
        print("\n❌ КРИТИЧНО: Исправления не найдены в коде!")
        print("Код не был изменён или файл был перезаписан!")
        print("НЕ ЗАПУСКАЙТЕ СЕРВЕР без исправлений!")
        return
    
    print("\n✅ Все исправления на месте!")
    
    print("\n" + "="*80)
    print("ШАГ 3: ЗАПУСК НОВОГО СЕРВЕРА")
    print("="*80)
    
    if not start_mtrade():
        print("\n❌ Не удалось запустить сервер!")
        print("Запустите вручную: python mTrade.py")
        return
    
    print("\n" + "="*80)
    print("✅ ПЕРЕЗАПУСК ЗАВЕРШЁН")
    print("="*80)
    print()
    print("СЛЕДУЮЩИЕ ШАГИ:")
    print("1. Проверьте логи сервера на наличие [LOCK_INIT]")
    print("2. Проведите тест: продажа → сброс цикла → проверка покупок")
    print("3. Если проблема повторится - запустите диагностику:")
    print("   python diagnose_double_start_buy.py")
    print()

if __name__ == '__main__':
    try:
        import psutil
    except ImportError:
        print("❌ Требуется модуль psutil!")
        print("Установите: pip install psutil")
        sys.exit(1)
    
    main()
