"""
Монитор двойных стартовых покупок
Анализирует логи в реальном времени и определяет двойные покупки
"""
import re
import time
from collections import defaultdict
from pathlib import Path

def monitor_double_buys():
    """Мониторит двойные стартовые покупки в логах"""
    print("=" * 80)
    print("🔍 МОНИТОР ДВОЙНЫХ СТАРТОВЫХ ПОКУПОК")
    print("=" * 80)
    print("Анализирую последние сделки из trade_logger...")
    print()
    
    # Ищем файл лога
    log_files = list(Path('.').glob('trade_log_*.txt'))
    if not log_files:
        print("❌ Файлы логов не найдены")
        return
    
    # Берём последний лог
    latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
    print(f"📄 Анализирую: {latest_log}")
    print()
    
    # Читаем последние 1000 строк
    try:
        with open(latest_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-1000:]
    except Exception as e:
        print(f"❌ Ошибка чтения лога: {e}")
        return
    
    # Парсим сделки
    # Формат: [13:47:51] [LTC] Buy{9.9675; Курс:84.4700; ↓Δ%:0.00; ↓%:0.00; Инвест:10.0000}
    buy_pattern = re.compile(r'\[(\d{2}:\d{2}:\d{2})\] \[([A-Z0-9]+)\] Buy\{([^;]+); Курс:([^;]+); [^}]+Инвест:([^}]+)\}')
    sell_pattern = re.compile(r'\[(\d{2}:\d{2}:\d{2})\] \[([A-Z0-9]+)\] Sell\{')
    
    # Собираем покупки по валютам
    buys_by_currency = defaultdict(list)
    sells_by_currency = defaultdict(list)
    
    for line in lines:
        buy_match = buy_pattern.search(line)
        if buy_match:
            timestamp, currency, volume, rate, invest = buy_match.groups()
            buys_by_currency[currency].append({
                'time': timestamp,
                'volume': float(volume),
                'rate': float(rate),
                'invest': float(invest),
                'line': line.strip()
            })
        
        sell_match = sell_pattern.search(line)
        if sell_match:
            timestamp, currency = sell_match.groups()
            sells_by_currency[currency].append({
                'time': timestamp,
                'line': line.strip()
            })
    
    # Анализируем двойные покупки
    print("🔍 АНАЛИЗ СТАРТОВЫХ ПОКУПОК:")
    print("-" * 80)
    
    found_doubles = False
    
    for currency in sorted(buys_by_currency.keys()):
        buys = buys_by_currency[currency]
        sells = sells_by_currency[currency]
        
        # Ищем пары стартовых покупок (инвест около 10.0)
        start_buys = [b for b in buys if 9.0 <= b['invest'] <= 11.0]
        
        if len(start_buys) < 2:
            continue
        
        # Проверяем, есть ли две покупки подряд без продажи между ними
        for i in range(len(start_buys) - 1):
            buy1 = start_buys[i]
            buy2 = start_buys[i + 1]
            
            # Парсим время
            h1, m1, s1 = map(int, buy1['time'].split(':'))
            h2, m2, s2 = map(int, buy2['time'].split(':'))
            time1 = h1 * 3600 + m1 * 60 + s1
            time2 = h2 * 3600 + m2 * 60 + s2
            diff = time2 - time1
            
            # Если разница меньше 30 секунд - это подозрительно
            if 0 < diff < 30:
                # Проверяем, была ли продажа между ними
                sell_between = False
                for sell in sells:
                    hs, ms, ss = map(int, sell['time'].split(':'))
                    time_sell = hs * 3600 + ms * 60 + ss
                    if time1 < time_sell < time2:
                        sell_between = True
                        break
                
                if not sell_between:
                    print(f"\n⚠️  НАЙДЕНА ДВОЙНАЯ СТАРТОВАЯ ПОКУПКА: {currency}")
                    print(f"   Разница: {diff} секунд")
                    print(f"   Первая:  {buy1['line']}")
                    print(f"   Вторая:  {buy2['line']}")
                    found_doubles = True
    
    if not found_doubles:
        print("✅ Двойных стартовых покупок не обнаружено")
    
    print("\n" + "=" * 80)
    print("💡 РЕКОМЕНДАЦИИ:")
    print("-" * 80)
    if found_doubles:
        print("1. Перезапустите сервер: python stop.py && python mTrade.py")
        print("2. Проверьте логи автотрейдера на наличие сообщений [PROTECTION]")
        print("3. Убедитесь, что исправления применены (проверьте дату изменения autotrader.py)")
    else:
        print("✅ Защита от двойных покупок работает корректно!")
    print("=" * 80)

if __name__ == '__main__':
    monitor_double_buys()
