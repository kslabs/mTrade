#!/usr/bin/env python3
"""Быстрая проверка состояния ETH цикла"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:5000"
BASE_CURRENCY = "ETH"

print(f"\n{'='*70}")
print(f"ПРОВЕРКА СОСТОЯНИЯ ЦИКЛА {BASE_CURRENCY}")
print(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'='*70}\n")

# 1. Проверяем API статистики
print("1. API СТАТИСТИКА (/api/autotrader/stats):")
print("-" * 70)
try:
    response = requests.get(f"{BASE_URL}/api/autotrader/stats", params={"base_currency": BASE_CURRENCY}, timeout=5)
    print(f"   HTTP Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"   Success: {data.get('success')}")
        
        if data.get("success"):
            stats = data.get("stats", {})
            print(f"\n   Статус цикла:")
            print(f"   - Активен (active): {stats.get('active')}")
            print(f"   - Состояние (state): {stats.get('state')}")
            print(f"   - Активный шаг (active_step): {stats.get('active_step')}")
            print(f"   - Включен (enabled): {stats.get('enabled')}")
            print(f"   - Базовый объём: {stats.get('base_volume')}")
            print(f"   - Последняя цена покупки: {stats.get('last_buy_price')}")
            print(f"   - Инвестировано: {stats.get('total_invested_usd')} USDT")
        else:
            print(f"   Error: {data.get('error')}")
    else:
        print(f"   Ошибка: {response.text}")
except Exception as e:
    print(f"   [ERROR] Не удалось подключиться к API: {e}")

# 2. Проверяем файл состояния
print(f"\n2. ФАЙЛ СОСТОЯНИЯ (autotrader_cycles_state.json):")
print("-" * 70)
try:
    with open("autotrader_cycles_state.json", "r", encoding="utf-8") as f:
        state = json.load(f)
    
    if BASE_CURRENCY in state:
        cycle = state[BASE_CURRENCY]
        print(f"   Найден цикл для {BASE_CURRENCY}:")
        print(f"   - active: {cycle.get('active')}")
        print(f"   - active_step: {cycle.get('active_step')}")
        print(f"   - status: {cycle.get('status', 'N/A')}")
        print(f"   - manual_pause: {cycle.get('manual_pause', False)}")
        print(f"   - last_buy_price: {cycle.get('last_buy_price')}")
        print(f"   - start_price: {cycle.get('start_price')}")
        print(f"   - total_invested_usd: {cycle.get('total_invested_usd')}")
        print(f"   - base_volume: {cycle.get('base_volume')}")
        
        if 'start_buy_order' in cycle:
            print(f"   - start_buy_order: {cycle.get('start_buy_order')}")
    else:
        print(f"   Цикл для {BASE_CURRENCY} НЕ НАЙДЕН в файле состояния")
        print(f"   Доступные валюты: {list(state.keys())}")
        
except FileNotFoundError:
    print(f"   [ERROR] Файл autotrader_cycles_state.json не найден")
except Exception as e:
    print(f"   [ERROR] Ошибка чтения файла: {e}")

# 3. Проверяем доступные циклы
print(f"\n3. ВСЕ ДОСТУПНЫЕ ЦИКЛЫ:")
print("-" * 70)
try:
    response = requests.get(f"{BASE_URL}/api/autotrader/cycles", timeout=5)
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            cycles = data.get("cycles", {})
            print(f"   Всего циклов: {len(cycles)}")
            for currency, info in cycles.items():
                print(f"   - {currency}: active={info.get('active')}, step={info.get('active_step')}, state={info.get('state')}")
        else:
            print(f"   Error: {data.get('error')}")
    else:
        print(f"   HTTP {response.status_code}: {response.text}")
except Exception as e:
    print(f"   [ERROR] {e}")

print(f"\n{'='*70}")
print("ДИАГНОСТИКА ЗАВЕРШЕНА")
print(f"{'='*70}\n")

# Выводим рекомендации
print("ЧТО ДОЛЖНО ПРОИЗОЙТИ ПРИ СБРОСЕ ЦИКЛА:")
print("-" * 70)
print("1. API должен вернуть success: true")
print("2. В консоли сервера должны появиться строки:")
print("   [RESET_CYCLE][ETH] Цикл сброшен в IDLE (ручной сброс, автостарт заблокирован)")
print("3. В файле состояния должно измениться:")
print("   - status: 'idle' или подобное")
print("   - manual_pause: true")
print("   - active: false")
print("4. В веб-интерфейсе статус должен показать 'IDLE' или 'Остановлен'")
print()
print("ЕСЛИ НИЧЕГО НЕ МЕНЯЕТСЯ:")
print("-" * 70)
print("- Возможно, сервер НЕ использует AutoTraderV2")
print("- Возможно, используется старый autotrader.py")
print("- Проверьте консоль сервера на наличие ошибок")
print("- Проверьте, что AUTO_TRADER инициализирован")
print()
