#!/usr/bin/env python3
"""
Тест кнопок reset и resume цикла для всех валют
Проверяет, что API endpoints работают мгновенно без 503 ошибок
"""

import requests
import time
import json

BASE_URL = "http://localhost:5000"

def test_reset_cycle(currency):
    """Тест reset cycle"""
    print(f"\n{'='*60}")
    print(f"Тестирование RESET для {currency}")
    print(f"{'='*60}")
    
    url = f"{BASE_URL}/api/autotrader/reset_cycle"
    payload = {"base_currency": currency}
    
    start = time.time()
    try:
        response = requests.post(url, json=payload, timeout=5)
        elapsed = time.time() - start
        
        print(f"Время ответа: {elapsed:.3f} сек")
        print(f"Статус: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"OK SUCCESS")
            print(f"Сообщение: {data.get('message', 'N/A')}")
            print(f"Старое состояние: {data.get('old_state', 'N/A')}")
            print(f"Новое состояние: {data.get('new_state', 'N/A')}")
            return True
        elif response.status_code == 503:
            print(f"FAIL: 503 Service Unavailable")
            print(f"Ответ: {response.text}")
            return False
        else:
            print(f"Неожиданный статус: {response.status_code}")
            print(f"Ответ: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        print(f"❌ TIMEOUT после {elapsed:.3f} сек")
        return False
    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ ERROR после {elapsed:.3f} сек: {e}")
        return False

def test_resume_cycle(currency):
    """Тест resume cycle"""
    print(f"\n{'='*60}")
    print(f"Тестирование RESUME для {currency}")
    print(f"{'='*60}")
    
    url = f"{BASE_URL}/api/autotrader/resume_cycle"
    payload = {"base_currency": currency}
    
    start = time.time()
    try:
        response = requests.post(url, json=payload, timeout=5)
        elapsed = time.time() - start
        
        print(f"Время ответа: {elapsed:.3f} сек")
        print(f"Статус: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"OK SUCCESS")
            print(f"Сообщение: {data.get('message', 'N/A')}")
            print(f"Был на паузе: {data.get('was_paused', 'N/A')}")
            print(f"Новое состояние: {data.get('new_state', 'N/A')}")
            return True
        elif response.status_code == 503:
            print(f"FAIL: 503 Service Unavailable")
            print(f"Ответ: {response.text}")
            return False
        else:
            print(f"Неожиданный статус: {response.status_code}")
            print(f"Ответ: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        print(f"❌ TIMEOUT после {elapsed:.3f} сек")
        return False
    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ ERROR после {elapsed:.3f} сек: {e}")
        return False

def get_currencies():
    """Получить список валют из app_state.json"""
    try:
        with open('app_state.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            perms = data.get('trading_permissions', {})
            # Возвращаем только те валюты, у которых разрешена торговля
            return [curr for curr, enabled in perms.items() if enabled]
    except Exception as e:
        print(f"Не удалось прочитать app_state.json: {e}")
        return ["BTC", "ETH", "TRX"]  # Fallback

def main():
    """Главная функция"""
    print("="*60)
    print("  ТЕСТ API ENDPOINTS: RESET & RESUME CYCLE")
    print("="*60)
    
    # Получаем список валют
    currencies = get_currencies()
    print(f"\nНайдено валют для тестирования: {len(currencies)}")
    print(f"Валюты: {', '.join(currencies)}")
    
    results = {}
    
    # Тестируем каждую валюту
    for currency in currencies:
        print(f"\n\n{'#'*60}")
        print(f"# ВАЛЮТА: {currency}")
        print(f"{'#'*60}")
        
        # Тест RESET
        reset_ok = test_reset_cycle(currency)
        time.sleep(0.5)  # Небольшая пауза между запросами
        
        # Тест RESUME
        resume_ok = test_resume_cycle(currency)
        time.sleep(0.5)
        
        results[currency] = {
            'reset': reset_ok,
            'resume': resume_ok
        }
    
    # Итоги
    print(f"\n\n{'='*60}")
    print("ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print(f"{'='*60}")
    
    all_ok = True
    for currency, res in results.items():
        reset_icon = "[OK]" if res['reset'] else "[FAIL]"
        resume_icon = "[OK]" if res['resume'] else "[FAIL]"
        print(f"{currency:6s} | RESET: {reset_icon} | RESUME: {resume_icon}")
        
        if not res['reset'] or not res['resume']:
            all_ok = False
    
    print(f"\n{'='*60}")
    if all_ok:
        print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("API endpoints работают мгновенно и без ошибок")
    else:
        print("НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
        print("Проверьте логи выше для деталей")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
