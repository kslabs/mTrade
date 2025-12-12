#!/usr/bin/env python3
"""
Быстрая проверка последней продажи в логах автотрейдера
Показывает все ключевые параметры последней завершённой сделки
"""

import re
import sys
from pathlib import Path

def parse_sell_block(log_file):
    """Парсит лог и находит последний блок ПАРАМЕТРЫ ЗАПРОСА НА ПРОДАЖУ"""
    
    if not Path(log_file).exists():
        print(f"❌ Файл логов не найден: {log_file}")
        print()
        print("Возможные причины:")
        print("1. Автотрейдер не запущен с перенаправлением в файл")
        print("2. Неправильный путь к файлу логов")
        print()
        print("Запустите автотрейдер командой:")
        print("  python autotrader_v2.py 2>&1 | Tee-Object -FilePath autotrader.log")
        return None
    
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Ищем все блоки "ПАРАМЕТРЫ ЗАПРОСА НА ПРОДАЖУ"
    pattern = r'\[(\w+)\] 🔵 ={10} ПАРАМЕТРЫ ЗАПРОСА НА ПРОДАЖУ ={10}.*?(?=\[|\Z)'
    matches = list(re.finditer(pattern, content, re.DOTALL))
    
    if not matches:
        print("⚠️ Блоки 'ПАРАМЕТРЫ ЗАПРОСА НА ПРОДАЖУ' не найдены в логах")
        print()
        print("Возможные причины:")
        print("1. Ещё не было ни одной продажи с момента запуска")
        print("2. Логи автотрейдера не содержат новый код")
        print("3. Используется старая версия autotrader_v2.py")
        print()
        print("Проверьте код командой:")
        print("  python check_sell_logs.py")
        return None
    
    # Берём последний блок
    last_match = matches[-1]
    currency = last_match.group(1)
    block_text = last_match.group(0)
    
    # Парсим параметры из блока
    data = {'currency': currency}
    
    patterns = {
        'currency_pair': r'currency_pair: ([\w_]+)',
        'amount': r'amount: ([\d.]+) (\w+)',
        'current_price': r'Текущая цена рынка: ([\d.]+)',
        'target_price': r'Целевая цена продажи: ([\d.]+)',
        'start_price': r'Цена покупки \(start_price\): ([\d.]+)',
        'expected_delta': r'Ожидаемая дельта: ([\d.+-]+)%',
        'required_delta': r'Требуемая дельта \(из таблицы\): ([\d.+-]+)%',
        'expected_revenue': r'Ожидаемая выручка: ~([\d.]+) (\w+)',
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, block_text)
        if match:
            data[key] = match.groups() if len(match.groups()) > 1 else match.group(1)
    
    # Ищем соответствующий блок ФИНАНСОВЫЕ ПОКАЗАТЕЛИ
    finance_pattern = rf'\[{currency}\] 💰 ={10} ФИНАНСОВЫЕ ПОКАЗАТЕЛИ ={10}.*?(?=\[|\Z)'
    finance_match = re.search(finance_pattern, content[last_match.end():], re.DOTALL)
    
    if finance_match:
        finance_text = finance_match.group(0)
        
        finance_patterns = {
            'invested': r'Инвестировано: ([\d.]+)',
            'received': r'Получено: ([\d.]+)',
            'profit': r'Профит: ([-\d.]+) \w+ \(([-+\d.]+)%\)',
            'buy_price': r'Цена покупки: ([\d.]+)',
            'sell_price': r'Цена продажи: ([\d.]+)',
            'price_growth': r'Рост цены: ([-+\d.]+)%',
            'required_growth': r'Требуемый рост \(из таблицы\): ([-+\d.]+)%',
        }
        
        for key, pattern in finance_patterns.items():
            match = re.search(pattern, finance_text)
            if match:
                data[key] = match.groups() if len(match.groups()) > 1 else match.group(1)
    
    return data

def format_check(condition, label):
    """Форматирует результат проверки"""
    symbol = "✅" if condition else "❌"
    status = "OK" if condition else "ОШИБКА!"
    return f"{symbol} {label}: {status}"

def display_sell_info(data):
    """Выводит информацию о продаже в удобном формате"""
    
    currency = data.get('currency', 'N/A')
    
    print("=" * 70)
    print(f"  ПОСЛЕДНЯЯ ПРОДАЖА: {currency}")
    print("=" * 70)
    print()
    
    # Блок 1: Параметры ордера
    print("📋 ПАРАМЕТРЫ ОРДЕРА:")
    print(f"   Торговая пара: {data.get('currency_pair', 'N/A')}")
    
    if 'amount' in data:
        amount, unit = data['amount']
        print(f"   Объём: {amount} {unit}")
    
    print()
    
    # Блок 2: Цены
    print("💵 ЦЕНЫ:")
    print(f"   Цена покупки (start):  {data.get('start_price', 'N/A')}")
    print(f"   Целевая цена:          {data.get('target_price', 'N/A')}")
    print(f"   Текущая цена (рынок):  {data.get('current_price', 'N/A')}")
    
    if 'sell_price' in data:
        print(f"   Цена продажи (факт):   {data.get('sell_price', 'N/A')}")
    
    print()
    
    # Блок 3: Дельты (САМОЕ ВАЖНОЕ!)
    print("📊 ДЕЛЬТЫ (критическая проверка!):")
    
    expected_delta = float(data.get('expected_delta', 0))
    required_delta = float(data.get('required_delta', 0))
    
    print(f"   Ожидаемая дельта:  {expected_delta:+.2f}%")
    print(f"   Требуемая дельта:  {required_delta:+.2f}%")
    
    if 'price_growth' in data:
        actual_growth = float(data.get('price_growth', 0))
        print(f"   Фактический рост:  {actual_growth:+.2f}%")
    
    print()
    
    # Блок 4: Финансы
    if 'invested' in data:
        print("💰 ФИНАНСЫ:")
        print(f"   Инвестировано: {data.get('invested', 'N/A')} USDT")
        print(f"   Получено:      {data.get('received', 'N/A')} USDT")
        
        if 'profit' in data:
            profit_abs, profit_pct = data['profit']
            print(f"   Профит:        {profit_abs} USDT ({profit_pct}%)")
        
        print()
    
    # Блок 5: Проверки
    print("=" * 70)
    print("  КРИТИЧЕСКИЕ ПРОВЕРКИ:")
    print("=" * 70)
    print()
    
    # Проверка 1: Дельта достигнута
    delta_ok = expected_delta >= required_delta
    print(format_check(delta_ok, f"Дельта достигнута ({expected_delta:.2f}% >= {required_delta:.2f}%)"))
    
    # Проверка 2: Цена выше покупки
    if 'current_price' in data and 'start_price' in data:
        current = float(data['current_price'])
        start = float(data['start_price'])
        price_ok = current > start
        print(format_check(price_ok, f"Цена выше покупки ({current:.4f} > {start:.4f})"))
    
    # Проверка 3: Целевая цена выше покупки
    if 'target_price' in data and 'start_price' in data:
        target = float(data['target_price'])
        start = float(data['start_price'])
        target_ok = target > start
        print(format_check(target_ok, f"Целевая цена выше покупки ({target:.4f} > {start:.4f})"))
    
    # Проверка 4: Профит положительный
    if 'profit' in data:
        profit_abs, profit_pct = data['profit']
        profit_ok = float(profit_abs) > 0
        print(format_check(profit_ok, f"Профит положительный ({profit_abs} USDT)"))
    
    # Проверка 5: Рост цены положительный
    if 'price_growth' in data:
        growth = float(data['price_growth'])
        growth_ok = growth > 0
        print(format_check(growth_ok, f"Рост цены положительный ({growth:+.2f}%)"))
    
    # Проверка 6: Рост >= требуемому
    if 'price_growth' in data and 'required_growth' in data:
        actual = float(data['price_growth'])
        required = float(data['required_growth'])
        growth_match_ok = actual >= required
        print(format_check(growth_match_ok, f"Рост >= требуемому ({actual:+.2f}% >= {required:+.2f}%)"))
    
    print()
    print("=" * 70)
    
    # Итоговая оценка
    checks = [delta_ok]
    if 'profit' in data:
        checks.append(float(data['profit'][0]) > 0)
    if 'price_growth' in data:
        checks.append(float(data['price_growth']) > 0)
    
    if all(checks):
        print("  ✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ - ПРОДАЖА КОРРЕКТНА!")
    else:
        print("  ❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ - ТРЕБУЕТСЯ АНАЛИЗ!")
    
    print("=" * 70)

def main():
    log_file = "autotrader.log"
    
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
    
    print()
    print("🔍 Поиск последней продажи в логах...")
    print(f"   Файл: {log_file}")
    print()
    
    data = parse_sell_block(log_file)
    
    if data:
        display_sell_info(data)
    else:
        print()
        print("💡 Подсказка:")
        print("   1. Убедитесь, что автотрейдер запущен")
        print("   2. Дождитесь первой продажи")
        print("   3. Запустите этот скрипт снова")
        print()

if __name__ == "__main__":
    main()
