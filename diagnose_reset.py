#!/usr/bin/env python3
"""Диагностика реальной проблемы со сбросом цикла"""

import requests
import json

BASE_URL = "http://localhost:5000"

print("\n" + "="*80)
print("ДИАГНОСТИКА ПРОБЛЕМЫ СО СБРОСОМ ЦИКЛА")
print("="*80 + "\n")

# Тест 1: Проверка доступности сервера
print("ТЕСТ 1: Проверка доступности сервера")
print("-"*80)
try:
    response = requests.get(f"{BASE_URL}/", timeout=2)
    print(f"Server OK (HTTP {response.status_code})")
except Exception as e:
    print(f"Server ERROR: {e}")
    exit(1)

# Тест 2: Проверка API статистики для BTC
print("\nTEST 2: API stats for BTC")
print("-"*80)
try:
    response = requests.get(f"{BASE_URL}/api/autotrader/stats", 
                          params={"base_currency": "BTC"}, 
                          timeout=5)
    print(f"HTTP Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
    else:
        print(f"Error Response: {response.text[:500]}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# Тест 3: Проверка API сброса для BTC
print("\nTEST 3: API reset for BTC")
print("-"*80)
try:
    response = requests.post(
        f"{BASE_URL}/api/autotrader/reset_cycle",
        headers={"Content-Type": "application/json"},
        json={"base_currency": "BTC"},
        timeout=5
    )
    print(f"HTTP Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
    else:
        print(f"Error: {response.text[:500]}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

print("\n" + "="*80)
