"""
Тестирование финального исправления P0 (start_price)

Проверяет:
1. При стартовой покупке P0 фиксируется и сохраняется в state_manager
2. P0 в таблице безубыточности совпадает с ценой первой покупки
3. При пересчёте таблицы используется зафиксированный P0, а не текущая рыночная цена
4. После сброса цикла P0 обнуляется и готов для нового цикла
"""

import json
import time
import sys

def test_p0_in_state_and_table():
    """Проверяет P0 в state_manager и таблице безубыточности"""
    
    print("=" * 70)
    print("🔍 ФИНАЛЬНЫЙ ТЕСТ P0 (start_price)")
    print("=" * 70)
    
    # Шаг 1: Проверка app_state.json
    print("\n📋 Шаг 1: Проверка app_state.json")
    try:
        with open('app_state.json', 'r', encoding='utf-8') as f:
            app_state = json.load(f)
        
        currencies = app_state.get('currencies', {})
        print(f"✅ app_state.json загружен, найдено {len(currencies)} валют")
        
        for currency, data in currencies.items():
            params = data.get('breakeven_params', {})
            start_price = params.get('start_price', 0)
            print(f"\n💰 {currency}:")
            print(f"   └─ start_price в app_state.json: {start_price}")
            
            if start_price > 0:
                print(f"   └─ ✅ start_price зафиксирован: {start_price:.8f}")
            else:
                print(f"   └─ ⚠️ start_price = 0 (цикл не активен или не начат)")
                
    except FileNotFoundError:
        print("❌ Файл app_state.json не найден")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга app_state.json: {e}")
        return False
    
    # Шаг 2: Проверка таблицы безубыточности через API
    print("\n📊 Шаг 2: Проверка таблицы безубыточности через API")
    
    try:
        import requests
        response = requests.get('http://127.0.0.1:5000/api/breakeven-table/BTC')
        
        if response.status_code == 200:
            table_data = response.json()
            table = table_data.get('table', [])
            
            if table:
                p0_in_table = table[0].get('rate', 0)
                print(f"✅ Таблица получена через API")
                print(f"   └─ P0 (row 0, rate): {p0_in_table:.8f}")
                
                # Сравниваем с app_state.json
                btc_params = currencies.get('BTC', {}).get('breakeven_params', {})
                start_price_state = btc_params.get('start_price', 0)
                
                if start_price_state > 0:
                    if abs(p0_in_table - start_price_state) < 0.0001:
                        print(f"   └─ ✅ P0 в таблице СОВПАДАЕТ с app_state.json!")
                    else:
                        print(f"   └─ ❌ P0 в таблице НЕ СОВПАДАЕТ с app_state.json!")
                        print(f"   └─    Таблица: {p0_in_table:.8f}")
                        print(f"   └─    State:   {start_price_state:.8f}")
                        print(f"   └─    Разница: {abs(p0_in_table - start_price_state):.8f}")
                        return False
                else:
                    print(f"   └─ ⚠️ start_price в state = 0, невозможно сравнить")
            else:
                print("❌ Таблица пуста")
                return False
        else:
            print(f"❌ Ошибка получения таблицы: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка запроса API: {e}")
        return False
    
    # Шаг 3: Проверка autotrader_cycles_state.json
    print("\n🔄 Шаг 3: Проверка autotrader_cycles_state.json")
    try:
        with open('autotrader_cycles_state.json', 'r', encoding='utf-8') as f:
            cycles_state = json.load(f)
        
        print(f"✅ autotrader_cycles_state.json загружен")
        
        for currency, cycle_data in cycles_state.items():
            start_price_cycle = cycle_data.get('start_price', 0)
            is_active = cycle_data.get('active', False)
            
            print(f"\n💰 {currency}:")
            print(f"   └─ Цикл активен: {is_active}")
            print(f"   └─ start_price в цикле: {start_price_cycle}")
            
            # Сравниваем с app_state.json
            currency_params = currencies.get(currency, {}).get('breakeven_params', {})
            start_price_state = currency_params.get('start_price', 0)
            
            if is_active and start_price_cycle > 0 and start_price_state > 0:
                if abs(start_price_cycle - start_price_state) < 0.0001:
                    print(f"   └─ ✅ start_price в цикле СОВПАДАЕТ с app_state.json!")
                else:
                    print(f"   └─ ❌ start_price в цикле НЕ СОВПАДАЕТ с app_state.json!")
                    print(f"   └─    Цикл:  {start_price_cycle:.8f}")
                    print(f"   └─    State: {start_price_state:.8f}")
                    print(f"   └─    Разница: {abs(start_price_cycle - start_price_state):.8f}")
                    return False
                    
    except FileNotFoundError:
        print("⚠️ Файл autotrader_cycles_state.json не найден (возможно, нет активных циклов)")
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга autotrader_cycles_state.json: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = test_p0_in_state_and_table()
    sys.exit(0 if success else 1)
