#!/usr/bin/env python3
"""Тест сброса цикла"""

import requests
import json

BASE_URL = "http://localhost:5000"

def test_reset_cycle():
    """Тестирует сброс цикла"""
    base_currency = "WLD"
    
    # 1. Получаем текущее состояние
    print(f"\n1. Получаем текущее состояние цикла {base_currency}...")
    response = requests.get(f"{BASE_URL}/api/autotrader/stats", params={"base_currency": base_currency})
    print(f"   Статус: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            stats = data.get("stats", {})
            print(f"   Активен: {stats.get('active')}")
            print(f"   Шаг: {stats.get('active_step')}")
            print(f"   Enabled: {stats.get('enabled')}")
            print(f"   Базовый объём: {stats.get('base_volume')}")
        else:
            print(f"   Ошибка: {data.get('error')}")
    else:
        print(f"   HTTP ошибка: {response.text}")
    
    # 2. Сбрасываем цикл
    print(f"\n2. Сбрасываем цикл {base_currency}...")
    response = requests.post(
        f"{BASE_URL}/api/autotrader/reset_cycle",
        headers={"Content-Type": "application/json"},
        json={"base_currency": base_currency}
    )
    print(f"   Статус: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"   Success: {data.get('success')}")
        print(f"   Message: {data.get('message')}")
        print(f"   Old state: {data.get('old_state')}")
        print(f"   New state: {data.get('new_state')}")
    else:
        print(f"   HTTP ошибка: {response.text}")
    
    # 3. Проверяем новое состояние
    print(f"\n3. Проверяем новое состояние цикла {base_currency}...")
    response = requests.get(f"{BASE_URL}/api/autotrader/stats", params={"base_currency": base_currency})
    print(f"   Статус: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            stats = data.get("stats", {})
            print(f"   Активен: {stats.get('active')}")
            print(f"   Шаг: {stats.get('active_step')}")
            print(f"   Enabled: {stats.get('enabled')}")
            print(f"   Базовый объём: {stats.get('base_volume')}")
        else:
            print(f"   Ошибка: {data.get('error')}")
    else:
        print(f"   HTTP ошибка: {response.text}")
    
    # 4. Проверяем индикаторы
    print(f"\n4. Проверяем индикаторы {base_currency}...")
    response = requests.get(f"{BASE_URL}/api/trade/indicators", params={"base_currency": base_currency, "quote_currency": "USDT"})
    print(f"   Статус: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            levels = data.get("autotrade_levels", {})
            print(f"   Активен цикл: {levels.get('active_cycle')}")
            print(f"   Шаг: {levels.get('active_step')}")
            print(f"   Базовый объём: {levels.get('base_volume')}")
            print(f"   Цена продажи: {levels.get('sell_price')}")
            print(f"   Цена покупки: {levels.get('next_buy_price')}")
        else:
            print(f"   Ошибка: {data.get('error')}")
    else:
        print(f"   HTTP ошибка: {response.text}")

if __name__ == "__main__":
    test_reset_cycle()
