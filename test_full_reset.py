"""
Полная проверка работы сброса цикла:
1. Текущее состояние
2. Сброс
3. Проверка в памяти
4. Проверка в файле
"""
import requests
import json
import time

BASE_URL = "http://localhost:5000"
CURRENCY = "ETH"

def check_reset_cycle():
    print("=" * 80)
    print("ПОЛНАЯ ПРОВЕРКА СБРОСА ЦИКЛА")
    print("=" * 80)
    print()
    
    # 1. Текущее состояние
    print("[1] Текущее состояние ETH:")
    try:
        r = requests.get(f"{BASE_URL}/api/autotrader/stats?base_currency={CURRENCY}")
        data = r.json()
        stats = data.get('stats', {})
        print(f"    Active: {stats.get('active')}")
        print(f"    Base Volume: {stats.get('base_volume')}")
        print(f"    State: {stats.get('state')}")
    except Exception as e:
        print(f"    Ошибка: {e}")
    
    print()
    
    # 2. Сброс цикла
    print("[2] Сброс цикла ETH:")
    try:
        r = requests.post(f"{BASE_URL}/api/autotrader/reset_cycle", json={"base_currency": CURRENCY})
        print(f"    HTTP Status: {r.status_code}")
        data = r.json()
        print(f"    Success: {data.get('success')}")
        if data.get('success'):
            print(f"    ✅ {data.get('message', '').split('.')[0]}")
        else:
            print(f"    ❌ Error: {data.get('error')}")
    except Exception as e:
        print(f"    Ошибка: {e}")
    
    print()
    time.sleep(0.5)
    
    # 3. Проверка в памяти
    print("[3] Состояние в памяти после сброса:")
    try:
        r = requests.get(f"{BASE_URL}/api/autotrader/stats?base_currency={CURRENCY}")
        data = r.json()
        stats = data.get('stats', {})
        active = stats.get('active')
        volume = stats.get('base_volume')
        state = stats.get('state')
        
        print(f"    Active: {active}")
        print(f"    Base Volume: {volume}")
        print(f"    State: {state}")
        
        if not active and volume == 0.0 and state == 'idle':
            print("    ✅ Состояние в памяти корректно сброшено")
        else:
            print("    ❌ Состояние в памяти не сброшено полностью")
    except Exception as e:
        print(f"    Ошибка: {e}")
    
    print()
    
    # 4. Проверка в файле
    print("[4] Состояние в файле после сброса:")
    try:
        with open('autotrader_cycles_state.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        eth = data.get('ETH', {})
        active = eth.get('active')
        volume = eth.get('base_volume')
        manual_pause = eth.get('manual_pause')
        
        print(f"    Active: {active}")
        print(f"    Base Volume: {volume}")
        print(f"    Manual Pause: {manual_pause}")
        
        if not active and volume == 0.0 and manual_pause:
            print("    ✅ Состояние в файле корректно сброшено")
        else:
            print("    ❌ Состояние в файле не соответствует ожиданиям")
    except Exception as e:
        print(f"    Ошибка: {e}")
    
    print()
    print("=" * 80)

if __name__ == "__main__":
    check_reset_cycle()
