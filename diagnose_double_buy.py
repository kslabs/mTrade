"""
Диагностика состояния автотрейдера после изменений
Проверяет, работают ли защиты от двойных покупок
"""
import json
import time
import os
from pathlib import Path

def check_autotrader_state():
    """Проверяет текущее состояние автотрейдера"""
    print("=" * 80)
    print("🔍 ДИАГНОСТИКА СОСТОЯНИЯ АВТОТРЕЙДЕРА")
    print("=" * 80)
    print()
    
    # Проверка 1: Файл состояния циклов
    cycles_file = Path('autotrader_cycles_state.json')
    if cycles_file.exists():
        print("✓ Файл autotrader_cycles_state.json найден")
        try:
            with open(cycles_file, 'r', encoding='utf-8') as f:
                cycles = json.load(f)
            
            if not cycles:
                print("  → Файл пустой (нет активных циклов)")
            else:
                print(f"  → Найдено валют: {len(cycles)}")
                for base, cycle in cycles.items():
                    print(f"\n  Валюта: {base}")
                    print(f"    - active: {cycle.get('active', False)}")
                    print(f"    - active_step: {cycle.get('active_step', -1)}")
                    print(f"    - base_volume: {cycle.get('base_volume', 0.0):.8f}")
                    print(f"    - pending_start: {cycle.get('pending_start', False)}")
                    
                    # КРИТИЧНО: Проверяем last_sell_time
                    last_sell = cycle.get('last_sell_time', 0)
                    if last_sell > 0:
                        elapsed = time.time() - last_sell
                        print(f"    - last_sell_time: {last_sell} (прошло {elapsed:.1f}с)")
                    else:
                        print(f"    - last_sell_time: НЕ УСТАНОВЛЕНО")
                    
                    # Проверяем last_start_attempt
                    last_start = cycle.get('last_start_attempt', 0)
                    if last_start > 0:
                        elapsed = time.time() - last_start
                        print(f"    - last_start_attempt: {last_start} (прошло {elapsed:.1f}с)")
        except Exception as e:
            print(f"  ✗ Ошибка чтения файла: {e}")
    else:
        print("✗ Файл autotrader_cycles_state.json НЕ найден")
    
    print()
    print("-" * 80)
    
    # Проверка 2: Код автотрейдера
    autotrader_file = Path('autotrader.py')
    if autotrader_file.exists():
        print("\n✓ Файл autotrader.py найден")
        
        # Проверяем наличие защиты
        with open(autotrader_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = {
            'ПРОВЕРКА ВРЕМЕНИ ПОСЛЕ ПОСЛЕДНЕЙ ПРОДАЖИ': False,
            'last_sell_time': False,
            'elapsed < 5': False,
            'pending_start': False,
            'Lock': False,
        }
        
        for key in checks:
            if key in content:
                checks[key] = True
        
        print("\n  Проверка защит в коде:")
        for key, found in checks.items():
            status = "✓" if found else "✗"
            print(f"    {status} {key}")
    else:
        print("\n✗ Файл autotrader.py НЕ найден")
    
    print()
    print("-" * 80)
    
    # Проверка 3: Обработчик продажи
    quick_trades_file = Path('handlers/quick_trades.py')
    if quick_trades_file.exists():
        print("\n✓ Файл handlers/quick_trades.py найден")
        
        with open(quick_trades_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = {
            'last_sell_time': False,
            'pending_start': False,
            'MANUAL_SELL': False,
        }
        
        for key in checks:
            if key in content:
                checks[key] = True
        
        print("\n  Проверка установки флагов при продаже:")
        for key, found in checks.items():
            status = "✓" if found else "✗"
            print(f"    {status} {key}")
    else:
        print("\n✗ Файл handlers/quick_trades.py НЕ найден")
    
    print()
    print("=" * 80)
    print("\n🔧 РЕКОМЕНДАЦИИ:\n")
    
    # Рекомендации
    recommendations = []
    
    # Проверяем процесс
    try:
        import psutil
        python_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'python' in proc.info['name'].lower():
                    cmdline = proc.info['cmdline']
                    if cmdline and any('mTrade' in str(c) or 'app.py' in str(c) for c in cmdline):
                        python_processes.append(proc.info)
            except:
                pass
        
        if python_processes:
            print(f"⚠️  Найдено запущенных процессов Python с mTrade: {len(python_processes)}")
            recommendations.append("КРИТИЧНО: Остановите сервер командой 'python stop.py' или 'taskkill /F /IM python.exe'")
            recommendations.append("Затем запустите заново: 'python mTrade.py'")
        else:
            print("✓ Нет запущенных процессов Python с mTrade")
            recommendations.append("Запустите сервер: 'python mTrade.py'")
    except ImportError:
        print("⚠️  Модуль psutil не установлен, не могу проверить процессы")
        recommendations.append("Проверьте вручную: tasklist | findstr python")
        recommendations.append("Остановите все процессы: taskkill /F /IM python.exe")
    
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    check_autotrader_state()
