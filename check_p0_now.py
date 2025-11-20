"""
Быстрая проверка текущего P0
"""
import requests
import json

BASE_URL = "http://localhost:5000"
BASE_CURRENCY = "DOGE"
QUOTE_CURRENCY = "USDT"

print("\n" + "="*60)
print("ПРОВЕРКА ТЕКУЩЕГО СОСТОЯНИЯ P0")
print("="*60)

# Получаем market_data
url = f"{BASE_URL}/api/market_data/{BASE_CURRENCY}_{QUOTE_CURRENCY}"
try:
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        data = response.json()
        levels = data.get('autotrade_levels', {})
        
        print(f"\n📊 AUTOTRADE LEVELS:")
        print(f"  active_cycle:    {levels.get('active_cycle', 'НЕТ')}")
        print(f"  active_step:     {levels.get('active_step', 'НЕТ')}")
        print(f"  start_price:     {levels.get('start_price', 'НЕТ')}")
        print(f"  last_buy_price:  {levels.get('last_buy_price', 'НЕТ')}")
        print(f"  current_price:   {levels.get('current_price', 'НЕТ')}")
        
    else:
        print(f"❌ Ошибка получения market_data: {response.status_code}")
except Exception as e:
    print(f"❌ Исключение: {e}")

# Получаем таблицу безубыточности
table_url = f"{BASE_URL}/api/breakeven_table/{BASE_CURRENCY}_{QUOTE_CURRENCY}"
try:
    table_response = requests.get(table_url, timeout=10)
    if table_response.status_code == 200:
        table_data = table_response.json()
        table = table_data.get('table', [])
        
        if table and len(table) > 0:
            p0_in_table = table[0].get('rate', 0)
            print(f"\n📋 ТАБЛИЦА БЕЗУБЫТОЧНОСТИ:")
            print(f"  P0 (table[0]['rate']): {p0_in_table}")
            
            # Сравниваем
            if 'levels' in locals() and levels.get('last_buy_price'):
                last_buy = levels['last_buy_price']
                diff = abs(last_buy - p0_in_table)
                
                print(f"\n{'='*60}")
                print("СРАВНЕНИЕ:")
                print('='*60)
                print(f"Цена покупки (last_buy_price): {last_buy:.8f}")
                print(f"P0 в таблице (rate):            {p0_in_table:.8f}")
                print(f"Разница:                        {diff:.8f}")
                
                if diff < 0.00000001:
                    print("\n✅ ОТЛИЧНО! P0 совпадает с ценой покупки!")
                else:
                    print(f"\n❌ ОШИБКА! P0 НЕ совпадает! Разница: {diff:.8f}")
                print('='*60)
        else:
            print("❌ Таблица пустая")
    else:
        print(f"❌ Ошибка получения таблицы: {table_response.status_code}")
except Exception as e:
    print(f"❌ Исключение при получении таблицы: {e}")

print("\n" + "="*60 + "\n")
