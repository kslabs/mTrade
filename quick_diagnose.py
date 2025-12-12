"""
Простая диагностика производительности автотрейдера

Проверяет реальные задержки без изменения кода
"""

import time
import json
import os
from datetime import datetime

def check_logs():
    """Проверить логи на предмет задержек"""
    print("="*80)
    print("🔍 ДИАГНОСТИКА ПРОИЗВОДИТЕЛЬНОСТИ")
    print("="*80)
    print()
    
    # 1. Проверка файла состояния циклов
    cycles_file = 'autotrader_cycles_state.json'
    if os.path.exists(cycles_file):
        print("📊 Состояние циклов автотрейдера:")
        with open(cycles_file, 'r', encoding='utf-8') as f:
            cycles = json.load(f)
        
        active_cycles = {k: v for k, v in cycles.items() if v.get('active')}
        
        if active_cycles:
            print(f"   Активных циклов: {len(active_cycles)}")
            for currency, cycle in active_cycles.items():
                print(f"   • {currency}: шаг {cycle.get('active_step')}, "
                      f"invested ${cycle.get('total_invested_usd', 0):.2f}")
                
                # Проверяем возраст последнего обновления
                saved_at = cycle.get('saved_at', 0)
                if saved_at:
                    age = time.time() - saved_at
                    print(f"     Последнее обновление: {age:.1f} сек назад")
                    if age > 60:
                        print(f"     ⚠️ ВНИМАНИЕ: Давно не обновлялось (>{age/60:.1f} мин)")
        else:
            print("   Нет активных циклов")
    else:
        print("❌ Файл состояния не найден:", cycles_file)
    
    print()
    
    # 2. Проверка trade logs
    print("📝 Последние торговые операции:")
    trade_logs_file = 'trade_logs.json'
    if os.path.exists(trade_logs_file):
        with open(trade_logs_file, 'r', encoding='utf-8') as f:
            logs = json.load(f)
        
        if logs:
            # Берем последние 5 записей
            recent = logs[-5:]
            for log in recent:
                ts = log.get('timestamp', 0)
                age = time.time() - ts
                action = log.get('action', '?')
                currency = log.get('currency', '?')
                print(f"   • {datetime.fromtimestamp(ts).strftime('%H:%M:%S')} "
                      f"({age:.1f}с назад) - {action} {currency}")
            
            # Проверяем частоту операций
            if len(logs) >= 2:
                last_two = logs[-2:]
                time_diff = last_two[1].get('timestamp', 0) - last_two[0].get('timestamp', 0)
                if time_diff > 0:
                    print(f"   Интервал между последними операциями: {time_diff:.1f} секунд")
                    if time_diff > 300:  # 5 минут
                        print(f"   ⚠️ БОЛЬШАЯ ЗАДЕРЖКА между операциями!")
        else:
            print("   Логи пусты")
    else:
        print("   Файл логов не найден")
    
    print()
    
    # 3. Проверка параметров в mTrade.py
    print("⚙️ Параметры автотрейдера (из mTrade.py):")
    if os.path.exists('mTrade.py'):
        with open('mTrade.py', 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Ищем debounce_seconds
        if 'debounce_seconds=' in content:
            import re
            matches = re.findall(r'debounce_seconds\s*=\s*([\d.]+)', content)
            if matches:
                print(f"   debounce_seconds: {matches[0]} сек")
                value = float(matches[0])
                if value > 0.1:
                    print(f"   ⚠️ МЕДЛЕННО! Рекомендуется 0.005-0.01 сек")
        
        # Ищем max_urgent_per_cycle
        if 'max_urgent_per_cycle=' in content:
            matches = re.findall(r'max_urgent_per_cycle\s*=\s*(\d+)', content)
            if matches:
                print(f"   max_urgent_per_cycle: {matches[0]}")
    
    print()
    
    # 4. Проверка WebSocket соединений
    print("🌐 Проблемы с получением данных:")
    print("   Проверьте логи на наличие сообщений:")
    print("   • '⚠️ WS data отсутствует'")
    print("   • '⚠️ Ticker отсутствует'")
    print("   • '⚠️ Ошибка получения цены'")
    print()
    
    # 5. Рекомендации
    print("💡 ЧТО ПРОВЕРИТЬ:")
    print()
    print("1️⃣ Пинг до биржи:")
    print("   ping api.gateio.ws")
    print("   Должен быть <100мс. Если >500мс - используйте VPS ближе к бирже")
    print()
    print("2️⃣ Параметры в mTrade.py (строка ~1260):")
    print("   debounce_seconds=0.005  # должно быть 0.005-0.01")
    print("   max_urgent_per_cycle=10 # должно быть 10-20")
    print()
    print("3️⃣ Параметры в dual_thread_autotrader.py (строка ~138):")
    print("   cycle_sleep = 0.01  # должно быть 0.01")
    print()
    print("4️⃣ Проверьте количество активных валют:")
    print("   Если >20 валют - автотрейдер будет медленнее")
    print()
    print("5️⃣ Проверьте сеть:")
    print("   Возможно, биржа медленно отвечает (нагрузка, проблемы с сетью)")
    print()
    print("="*80)

def measure_api_speed():
    """Замерить скорость API запросов"""
    print("\n⏱️ ТЕСТ СКОРОСТИ API (публичный endpoint):")
    print()
    
    try:
        import requests
        
        # Тест 1: Простой GET запрос
        url = "https://api.gateio.ws/api/v4/spot/tickers?currency_pair=BTC_USDT"
        
        times = []
        for i in range(5):
            start = time.time()
            response = requests.get(url, timeout=10)
            elapsed = time.time() - start
            times.append(elapsed)
            status = "✅" if response.status_code == 200 else "❌"
            print(f"   Попытка {i+1}: {elapsed:.3f} сек {status}")
        
        avg = sum(times) / len(times)
        print(f"\n   Среднее время: {avg:.3f} сек")
        
        if avg > 1.0:
            print("   🔴 ОЧЕНЬ МЕДЛЕННО! Проблемы с сетью или биржа перегружена")
        elif avg > 0.5:
            print("   🟡 МЕДЛЕННО. Проверьте пинг и сеть")
        else:
            print("   🟢 Скорость нормальная")
        
    except Exception as e:
        print(f"   ❌ Ошибка теста: {e}")

if __name__ == '__main__':
    check_logs()
    measure_api_speed()
    
    print("\n" + "="*80)
    print("✅ Диагностика завершена")
    print("="*80)
