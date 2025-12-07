#!/usr/bin/env python3
"""
СРОЧНАЯ ПРОВЕРКА: Работают ли защиты в запущенном сервере?

Этот скрипт проверяет:
1. Применены ли исправления в коде
2. Активен ли сервер
3. Что показывают логи (если доступны)
"""
import os
import sys
from pathlib import Path
import psutil
from datetime import datetime

def check_code_fixes():
    """Проверка исправлений в коде"""
    print("="*80)
    print("ПРОВЕРКА #1: ИСПРАВЛЕНИЯ В КОДЕ")
    print("="*80)
    
    autotrader_path = Path('autotrader.py')
    if not autotrader_path.exists():
        print("❌ Файл autotrader.py не найден!")
        return False
    
    with open(autotrader_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    checks = {
        'Мастер-Lock в __init__': '_locks_creation_lock = Lock()' in code,
        'Использование with _locks_creation_lock': 'with self._locks_creation_lock:' in code,
        'Логирование [LOCK_INIT]': '[LOCK_INIT]' in code,
        'Логирование [PROTECTION]': '[PROTECTION]' in code,
        'Логирование [LOCK_PROTECTION]': '[LOCK_PROTECTION]' in code,
    }
    
    all_ok = True
    for check_name, result in checks.items():
        status = "✅" if result else "❌"
        print(f"  {status} {check_name}")
        if not result:
            all_ok = False
    
    return all_ok

def check_server_status():
    """Проверка статуса сервера"""
    print("\n" + "="*80)
    print("ПРОВЕРКА #2: СТАТУС СЕРВЕРА")
    print("="*80)
    
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            cmdline = proc.info.get('cmdline')
            if cmdline and any('mTrade.py' in str(arg) for arg in cmdline):
                processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if not processes:
        print("❌ Сервер mTrade НЕ ЗАПУЩЕН!")
        return False
    
    print(f"✅ Найдено процессов mTrade: {len(processes)}\n")
    
    for proc in processes:
        try:
            start_time = datetime.fromtimestamp(proc.info['create_time'])
            print(f"  PID: {proc.info['pid']}")
            print(f"  Запущен: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  Работает: {(datetime.now() - start_time).total_seconds() / 60:.1f} минут")
            print()
        except Exception as e:
            print(f"  Ошибка получения информации: {e}")
    
    return True

def analyze_current_state():
    """Анализ текущего состояния циклов"""
    print("="*80)
    print("ПРОВЕРКА #3: ТЕКУЩЕЕ СОСТОЯНИЕ ЦИКЛОВ")
    print("="*80)
    
    state_file = Path('autotrader_cycles_state.json')
    if not state_file.exists():
        print("❌ Файл autotrader_cycles_state.json не найден!")
        return
    
    import json
    with open(state_file, 'r', encoding='utf-8') as f:
        cycles = json.load(f)
    
    print(f"\nВсего валют: {len(cycles)}")
    print("\nПоследние изменения файла:")
    mtime = datetime.fromtimestamp(state_file.stat().st_mtime)
    print(f"  {mtime.strftime('%Y-%m-%d %H:%M:%S')} ({(datetime.now() - mtime).total_seconds() / 60:.1f} минут назад)")
    
    # Ищем подозрительные состояния
    print("\n🔍 Анализ подозрительных циклов:")
    
    suspicious = []
    for base, cycle in cycles.items():
        if not cycle.get('active'):
            continue
        
        base_volume = cycle.get('base_volume', 0.0)
        active_step = cycle.get('active_step', -1)
        
        # Очень маленький баланс при активном цикле
        if base_volume < 0.01:
            suspicious.append({
                'base': base,
                'reason': f'Маленький баланс ({base_volume:.8f}) при active=True',
                'cycle': cycle
            })
        
        # Pending_start при активном цикле
        if cycle.get('pending_start'):
            suspicious.append({
                'base': base,
                'reason': 'pending_start=True при active=True (невозможно!)',
                'cycle': cycle
            })
    
    if suspicious:
        print(f"\n⚠️ Найдено подозрительных циклов: {len(suspicious)}\n")
        for item in suspicious:
            print(f"  [{item['base']}] {item['reason']}")
    else:
        print("\n✅ Подозрительных циклов не найдено")

def check_protection_in_logs():
    """Проверка логов на наличие защитных сообщений"""
    print("\n" + "="*80)
    print("ПРОВЕРКА #4: ЛОГИ ЗАЩИТЫ")
    print("="*80)
    
    print("\n⚠️ ВАЖНО: Эта проверка работает только если:")
    print("  1. Логи пишутся в файл (trade_log_*.txt)")
    print("  2. Была хотя бы одна стартовая покупка после перезапуска")
    print()
    
    # Ищем файлы логов
    log_files = list(Path('.').glob('trade_log_*.txt'))
    
    if not log_files:
        print("⚠️ Файлы логов не найдены в текущей директории")
        print("   Логи могут писаться только в консоль")
        print()
        print("📋 ЧТО ДЕЛАТЬ:")
        print("  1. Откройте окно с запущенным сервером")
        print("  2. Прокрутите логи вверх")
        print("  3. Найдите стартовые покупки (Buy{...; ↓Δ%:0.00})")
        print("  4. Проверьте, есть ли ПЕРЕД ними:")
        print("     [LOCK_INIT][XXX] Создан новый Lock")
        print("     [PROTECTION][XXX] ФЛАГ pending_start=True")
        print()
        print("❓ Если этих сообщений НЕТ:")
        print("  → Защиты НЕ РАБОТАЮТ (несмотря на изменения в коде)")
        print("  → Нужна дополнительная диагностика")
        return
    
    print(f"✅ Найдено файлов логов: {len(log_files)}")
    
    # Анализируем последний файл
    latest_log = max(log_files, key=lambda p: p.stat().st_mtime)
    print(f"\nАнализ последнего лога: {latest_log.name}")
    print(f"Последнее изменение: {datetime.fromtimestamp(latest_log.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
    
    with open(latest_log, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Ищем защитные сообщения
    lock_init = content.count('[LOCK_INIT]')
    protection = content.count('[PROTECTION]')
    lock_protection = content.count('[LOCK_PROTECTION]')
    
    print(f"\nНайдено защитных сообщений:")
    print(f"  [LOCK_INIT]: {lock_init}")
    print(f"  [PROTECTION]: {protection}")
    print(f"  [LOCK_PROTECTION]: {lock_protection}")
    
    if lock_init == 0 and protection == 0:
        print("\n❌ ЗАЩИТНЫЕ СООБЩЕНИЯ НЕ НАЙДЕНЫ!")
        print("   Это означает:")
        print("   1. Не было стартовых покупок после перезапуска, ИЛИ")
        print("   2. Защиты не работают (код не применился)")
    else:
        print("\n✅ Защитные сообщения присутствуют!")
        print("   Защиты РАБОТАЮТ!")

def main():
    print("\n" + "="*80)
    print("СРОЧНАЯ ПРОВЕРКА: РАБОТАЮТ ЛИ ЗАЩИТЫ?")
    print("="*80)
    print()
    
    code_ok = check_code_fixes()
    print()
    
    server_ok = check_server_status()
    print()
    
    analyze_current_state()
    print()
    
    check_protection_in_logs()
    print()
    
    print("="*80)
    print("ИТОГ")
    print("="*80)
    
    if not code_ok:
        print("\n❌ КРИТИЧНО: Исправления НЕ ПРИМЕНЕНЫ в коде!")
        print("   Файл autotrader.py был изменён или перезаписан")
    elif not server_ok:
        print("\n❌ КРИТИЧНО: Сервер НЕ ЗАПУЩЕН!")
        print("   Запустите: python mTrade.py")
    else:
        print("\n✅ Код исправлен: Да")
        print("✅ Сервер запущен: Да")
        print()
        print("📋 СЛЕДУЮЩИЕ ШАГИ:")
        print()
        print("1. Откройте окно с запущенным сервером (консоль)")
        print()
        print("2. Дождитесь стартовой покупки любой валюты")
        print("   (Покупка с ↓Δ%:0.00)")
        print()
        print("3. Проверьте логи ПЕРЕД этой покупкой:")
        print()
        print("   ✅ Если видите:")
        print("      [LOCK_INIT][XXX] Создан новый Lock")
        print("      [PROTECTION][XXX] ФЛАГ pending_start=True")
        print("      → Защиты РАБОТАЮТ!")
        print()
        print("   ❌ Если НЕ видите:")
        print("      → Защиты НЕ РАБОТАЮТ")
        print("      → Нужна дополнительная диагностика")
        print()
        print("4. Проверьте, происходят ли двойные покупки:")
        print("   - После ручной продажи → сброс цикла")
        print("   - Должна быть ТОЛЬКО ОДНА покупка")
        print()

if __name__ == '__main__':
    try:
        import psutil
    except ImportError:
        print("❌ Требуется модуль psutil!")
        print("Установлен ли он? Попробуйте: pip install psutil")
        sys.exit(1)
    
    main()
