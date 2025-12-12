#!/usr/bin/env python3
"""
ОБЪЯСНЕНИЕ: Почему не работает сброс ETH цикла
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:5000"

print("\n" + "="*80)
print("ПРОБЛЕМА: При нажатии кнопки 'Сброс цикла' для ETH ничего не происходит")
print("="*80 + "\n")

# 1. Проверяем файл состояния
print("ШАБЛОН 1: Проверка файла autotrader_cycles_state.json")
print("-"*80)
try:
    with open("autotrader_cycles_state.json", "r", encoding="utf-8") as f:
        state = json.load(f)
    
    currencies = list(state.keys())
    print(f"✓ Найдено {len(currencies)} валют в файле состояния:")
    for curr in sorted(currencies):
        cycle = state[curr]
        print(f"  - {curr}: active={cycle.get('active')}, step={cycle.get('active_step')}")
    
    if "ETH" in currencies:
        print(f"\n✓ ETH найден в файле состояния")
    else:
        print(f"\n✗ ETH НЕ НАЙДЕН в файле состояния!")
        print(f"\nПРИЧИНА ПРОБЛЕМЫ #1:")
        print(f"  ETH не добавлен в автотрейдер.")
        print(f"  Автотрейдер работает только с валютами из этого файла.")
        
except Exception as e:
    print(f"✗ Ошибка чтения файла: {e}")

# 2. Проверяем API разрешений
print(f"\nШАГ 2: Проверка разрешений на торговлю (API)")
print("-"*80)
try:
    response = requests.get(f"{BASE_URL}/api/trading/permissions", timeout=3)
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            perms = data.get("permissions", {})
            print(f"✓ Разрешения получены для {len(perms)} валют:")
            
            eth_found = False
            for curr, enabled in sorted(perms.items()):
                status = "✓ Включен" if enabled else "✗ Выключен"
                print(f"  - {curr}: {status}")
                if curr == "ETH":
                    eth_found = True
            
            if not eth_found:
                print(f"\n✗ ETH НЕ НАЙДЕН в разрешениях!")
                print(f"\nПРИЧИНА ПРОБЛЕМЫ #2:")
                print(f"  ETH не включен в настройках разрешений торговли.")
                print(f"  Автотрейдер не будет обрабатывать эту валюту.")
            elif not perms.get("ETH"):
                print(f"\n⚠ ETH найден, но ВЫКЛЮЧЕН в разрешениях!")
        else:
            print(f"✗ API вернул ошибку: {data.get('error')}")
    else:
        print(f"✗ HTTP {response.status_code}")
except requests.exceptions.Timeout:
    print(f"✗ Таймаут при подключении к API (сервер завис?)")
except Exception as e:
    print(f"✗ Ошибка: {e}")

# 3. Проверяем app_state.json
print(f"\nШАГ 3: Проверка app_state.json (настройки приложения)")
print("-"*80)
try:
    with open("app_state.json", "r", encoding="utf-8") as f:
        app_state = json.load(f)
    
    if "trading_permissions" in app_state:
        perms = app_state["trading_permissions"]
        print(f"✓ Найдены разрешения для {len(perms)} валют:")
        
        eth_found = False
        for curr, enabled in sorted(perms.items()):
            status = "✓ Включен" if enabled else "✗ Выключен"
            print(f"  - {curr}: {status}")
            if curr == "ETH":
                eth_found = True
        
        if not eth_found:
            print(f"\n✗ ETH НЕ НАЙДЕН в app_state.json!")
    else:
        print(f"✗ Секция 'trading_permissions' не найдена в app_state.json")
        
except FileNotFoundError:
    print(f"✗ Файл app_state.json не найден")
except Exception as e:
    print(f"✗ Ошибка чтения: {e}")

# Итоговый вывод
print("\n" + "="*80)
print("ИТОГОВЫЙ ВЫВОД:")
print("="*80)
print("""
ВЕРОЯТНАЯ ПРИЧИНА:
  ETH не добавлен в список отслеживаемых валют автотрейдера.
  Автотрейдер работает только с валютами, которые:
  1. Перечислены в autotrader_cycles_state.json
  2. Имеют разрешение в app_state.json (trading_permissions)
  
ЧТО НУЖНО СДЕЛАТЬ:
  
  ВАРИАНТ 1: Добавить ETH через веб-интерфейс
  ------------------------------------------
  1. Откройте веб-интерфейс (http://localhost:5000)
  2. Найдите настройки валют
  3. Добавьте ETH в список отслеживаемых валют
  4. Включите разрешение на торговлю для ETH
  
  ВАРИАНТ 2: Использовать существующую валюту
  -------------------------------------------
  Выберите одну из уже активных валют для тестирования:
""")

try:
    with open("autotrader_cycles_state.json", "r", encoding="utf-8") as f:
        state = json.load(f)
    print("  Доступные валюты:")
    for curr in sorted(state.keys()):
        print(f"    - {curr}")
    print(f"\n  Измените BASE_CURRENCY в test_cycle_buttons.py на одну из этих валют.")
except:
    pass

print("\n" + "="*80)
print("Для детальной диагностики запустите:")
print("  python test_cycle_buttons.py")
print("с правильной валютой (например, BTC или SUI)")
print("="*80 + "\n")
