#!/usr/bin/env python3
"""
Быстрый тест reset/resume для одной валюты
"""

import requests
import time

BASE_URL = "http://localhost:5000"
CURRENCY = "BTC"

print(f"={'='*60}")
print(f"Тест RESET для {CURRENCY}")
print(f"={'='*60}")

# Test RESET
url = f"{BASE_URL}/api/autotrader/reset_cycle"
payload = {"base_currency": CURRENCY}

start = time.time()
try:
    response = requests.post(url, json=payload, timeout=5)
    elapsed = time.time() - start
    
    print(f"Время ответа: {elapsed:.3f} сек")
    print(f"Статус: {response.status_code}")
    print(f"Ответ: {response.text}")
    
    if response.status_code == 200:
        print("\n[OK] RESET сработал!")
    else:
        print(f"\n[FAIL] RESET не сработал (код {response.status_code})")
        
except Exception as e:
    elapsed = time.time() - start
    print(f"[ERROR] {e}")

# Test RESUME
print(f"\n{'='*60}")
print(f"Тест RESUME для {CURRENCY}")
print(f"={'='*60}")

time.sleep(0.5)

url = f"{BASE_URL}/api/autotrader/resume_cycle"
payload = {"base_currency": CURRENCY}

start = time.time()
try:
    response = requests.post(url, json=payload, timeout=5)
    elapsed = time.time() - start
    
    print(f"Время ответа: {elapsed:.3f} сек")
    print(f"Статус: {response.status_code}")
    print(f"Ответ: {response.text}")
    
    if response.status_code == 200:
        print("\n[OK] RESUME сработал!")
    else:
        print(f"\n[FAIL] RESUME не сработал (код {response.status_code})")
        
except Exception as e:
    elapsed = time.time() - start
    print(f"[ERROR] {e}")
