#!/usr/bin/env python3
"""Тест кнопок сброса и старта цикла"""

import requests
import time
import json

BASE_URL = "http://localhost:5000"
# ВАЖНО: Используйте валюту, которая есть в автотрейдере!
# Все 16 валют синхронизированы: ETH, SOL, LINK, WLD, ANIME, GT, BTC, SUI, ICP, ADA, TAO, LTC, XRP, XRP5L, BNB, DOGE
BASE_CURRENCY = "ETH"  # Теперь ETH добавлен! Можно тестировать

def get_cycle_status():
    """Получить текущий статус цикла"""
    response = requests.get(f"{BASE_URL}/api/autotrader/stats", params={"base_currency": BASE_CURRENCY})
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            stats = data.get("stats", {})
            return stats
    return None

def reset_cycle():
    """Сбросить цикл"""
    response = requests.post(
        f"{BASE_URL}/api/autotrader/reset_cycle",
        headers={"Content-Type": "application/json"},
        json={"base_currency": BASE_CURRENCY}
    )
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print(f"Ошибка HTTP {response.status_code}: {response.text}")
        return None

def resume_cycle():
    """Возобновить цикл"""
    response = requests.post(
        f"{BASE_URL}/api/autotrader/resume_cycle",
        headers={"Content-Type": "application/json"},
        json={"base_currency": BASE_CURRENCY}
    )
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print(f"Ошибка HTTP {response.status_code}: {response.text}")
        return None

def print_status(stats):
    """Вывести статус цикла"""
    if stats:
        print(f"  Активен: {stats.get('active')}")
        print(f"  Состояние: {stats.get('state')}")
        print(f"  Шаг: {stats.get('active_step')}")
        print(f"  Enabled: {stats.get('enabled')}")
        print(f"  Базовый объём: {stats.get('base_volume')}")
    else:
        print("  Нет данных")

def main():
    print(f"\n{'='*60}")
    print(f"Тест кнопок управления циклом для {BASE_CURRENCY}")
    print(f"{'='*60}\n")
    
    # 1. Проверяем текущий статус
    print("1. ТЕКУЩИЙ СТАТУС:")
    stats = get_cycle_status()
    print_status(stats)
    
    # 2. Сбрасываем цикл
    print(f"\n2. СБРОС ЦИКЛА...")
    result = reset_cycle()
    if result:
        print(f"  Success: {result.get('success')}")
        print(f"  Message: {result.get('message')}")
        print(f"  New state: {result.get('new_state')}")
    
    # Ждём 2 секунды
    time.sleep(2)
    
    # 3. Проверяем статус после сброса
    print(f"\n3. СТАТУС ПОСЛЕ СБРОСА:")
    stats = get_cycle_status()
    print_status(stats)
    
    # 4. Возобновляем цикл
    print(f"\n4. ВОЗОБНОВЛЕНИЕ ЦИКЛА...")
    result = resume_cycle()
    if result:
        print(f"  Success: {result.get('success')}")
        print(f"  Message: {result.get('message')}")
        print(f"  New state: {result.get('new_state')}")
    
    # Ждём 5 секунд для автостарта
    print(f"\n5. ОЖИДАНИЕ АВТОСТАРТА (5 секунд)...")
    for i in range(5, 0, -1):
        print(f"  {i}...", end="\r")
        time.sleep(1)
    print()
    
    # 6. Проверяем статус после возобновления
    print(f"\n6. СТАТУС ПОСЛЕ ВОЗОБНОВЛЕНИЯ:")
    stats = get_cycle_status()
    print_status(stats)
    
    print(f"\n{'='*60}")
    print("ТЕСТ ЗАВЕРШЁН")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
