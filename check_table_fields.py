"""
Проверка: используется ли сохранённая таблица или пересчитывается заново?
"""
import requests
import json

url = 'http://localhost:5000/api/trade/indicators?base_currency=ETH&quote_currency=USDT&include_table=1'

print("="*60)
print("ПРОВЕРКА ТАБЛИЦЫ БЕЗУБЫТОЧНОСТИ")
print("="*60)

try:
    response = requests.get(url)
    data = response.json()
    
    if not data.get('success'):
        print(f"❌ Ошибка API: {data.get('error')}")
        exit(1)
    
    table = data.get('autotrade_levels', {}).get('table', [])
    
    if not table:
        print("❌ Таблица не получена из API")
        exit(1)
    
    print(f"\n✅ Таблица получена: {len(table)} шагов")
    print(f"\nПоля в первой строке (step 0):")
    
    row0 = table[0]
    for key in sorted(row0.keys()):
        value = row0[key]
        print(f"  {key:30s}: {value}")
    
    # Проверяем наличие критических полей
    print(f"\n{'='*60}")
    print("ПРОВЕРКА КРИТИЧЕСКИХ ПОЛЕЙ:")
    print(f"{'='*60}")
    
    missing_fields = []
    
    if 'total_invested' not in row0 or row0['total_invested'] is None:
        missing_fields.append('total_invested')
        print(f"  ❌ total_invested: ОТСУТСТВУЕТ или None")
    else:
        print(f"  ✅ total_invested: {row0['total_invested']}")
    
    if 'breakeven_pct' not in row0 or row0['breakeven_pct'] is None:
        missing_fields.append('breakeven_pct')
        print(f"  ❌ breakeven_pct: ОТСУТСТВУЕТ или None")
    else:
        print(f"  ✅ breakeven_pct: {row0['breakeven_pct']}")
    
    # Сравниваем с файлом состояния
    print(f"\n{'='*60}")
    print("СРАВНЕНИЕ С ФАЙЛОМ СОСТОЯНИЯ:")
    print(f"{'='*60}")
    
    with open('autotrader_cycles_state.json', 'r', encoding='utf-8') as f:
        state_data = json.load(f)
    
    eth_cycle = state_data.get('ETH', {})
    saved_table = eth_cycle.get('table', [])
    
    if saved_table:
        saved_row0 = saved_table[0]
        print(f"\nФайл состояния (step 0):")
        print(f"  rate: {saved_row0.get('rate')}")
        print(f"  total_invested: {saved_row0.get('total_invested')}")
        print(f"  breakeven_pct: {saved_row0.get('breakeven_pct')}")
        
        # Проверяем, совпадают ли таблицы
        if row0.get('rate') == saved_row0.get('rate'):
            if row0.get('total_invested') == saved_row0.get('total_invested'):
                print(f"\n✅ ТАБЛИЦА ИСПОЛЬЗУЕТСЯ ИЗ ФАЙЛА (rate и total_invested совпадают)")
            else:
                print(f"\n⚠️ rate совпадает, но total_invested ОТЛИЧАЕТСЯ:")
                print(f"  API: {row0.get('total_invested')}")
                print(f"  Файл: {saved_row0.get('total_invested')}")
                print(f"  ВЫВОД: Таблица ПЕРЕСЧИТАНА ЗАНОВО")
        else:
            print(f"\n❌ ТАБЛИЦА ПЕРЕСЧИТАНА С ДРУГОЙ ЦЕНОЙ:")
            print(f"  API rate: {row0.get('rate')}")
            print(f"  Файл rate: {saved_row0.get('rate')}")
    
    if missing_fields:
        print(f"\n{'='*60}")
        print(f"❌ ПРОБЛЕМА: Отсутствуют поля: {', '.join(missing_fields)}")
        print(f"{'='*60}")
        print(f"\nВОЗМОЖНЫЕ ПРИЧИНЫ:")
        print(f"  1. Таблица пересчитывается заново вместо использования сохранённой")
        print(f"  2. API фильтрует поля при возврате (проверьте mTrade.py, строка с include_table)")
        print(f"  3. Таблица в памяти не содержит этих полей")
    else:
        print(f"\n{'='*60}")
        print(f"✅ ВСЕ ПОЛЯ ПРИСУТСТВУЮТ")
        print(f"{'='*60}")

except Exception as e:
    print(f"\n❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
