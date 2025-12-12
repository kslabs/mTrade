"""
Диагностика состояния AUTO_TRADER в памяти через API.
Запрашивает детальную информацию о цикле ETH через API и выводит её.
"""

import requests
import json

API_BASE_URL = "http://127.0.0.1:5000"

def diagnose_autotrader_memory():
    """Диагностика состояния AUTO_TRADER через API"""
    print("=" * 80)
    print("ДИАГНОСТИКА ПАМЯТИ AUTO_TRADER ЧЕРЕЗ API")
    print("=" * 80)
    print()
    
    # 1. Проверяем общий статус автотрейдера
    print("[1] Общий статус автотрейдера:")
    try:
        resp = requests.get(f"{API_BASE_URL}/api/autotrade/status", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"❌ Ошибка: HTTP {resp.status_code}")
            print(resp.text)
    except Exception as e:
        print(f"❌ Исключение: {e}")
    print()
    
    # 2. Запрашиваем статистику для ETH
    print("[2] Статистика цикла ETH:")
    try:
        resp = requests.get(f"{API_BASE_URL}/api/autotrader/stats?base_currency=ETH", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # Анализируем данные
            print()
            print("=" * 80)
            print("АНАЛИЗ ДАННЫХ:")
            print("=" * 80)
            if data.get('success'):
                stats = data.get('stats', {})
                print(f"✅ Запрос успешен")
                print(f"   - Валюта: {stats.get('base_currency')}")
                print(f"   - Автотрейдер включен: {stats.get('enabled')}")
                print(f"   - Автотрейдер запущен: {stats.get('running')}")
                print(f"   - Версия: {stats.get('version')}")
                print(f"   - Состояние цикла: {stats.get('state', 'НЕ УКАЗАНО')}")
                print(f"   - Цикл активен: {stats.get('active', False)}")
                print(f"   - Шаг цикла: {stats.get('active_step', -1)}")
                print(f"   - Стартовая цена: {stats.get('start_price', 0.0)}")
                print(f"   - Последняя цена покупки: {stats.get('last_buy_price', 0.0)}")
                print(f"   - Объём базовой валюты: {stats.get('base_volume', 0.0)}")
                print(f"   - Инвестировано USD: {stats.get('total_invested_usd', 0.0)}")
                print(f"   - Последнее действие: {stats.get('last_action_at', 0.0)}")
                
                # Проверка несоответствий
                print()
                print("=" * 80)
                print("ПРОВЕРКА НЕСООТВЕТСТВИЙ:")
                print("=" * 80)
                
                if not stats.get('active'):
                    print("⚠️  ПРОБЛЕМА: Цикл НЕ АКТИВЕН (active=false)")
                else:
                    print("✅ Цикл активен")
                
                if stats.get('base_volume', 0.0) == 0.0:
                    print("⚠️  ПРОБЛЕМА: Объём базовой валюты = 0 (должен быть > 0 после покупки)")
                else:
                    print(f"✅ Объём базовой валюты: {stats.get('base_volume')}")
                
                if stats.get('total_invested_usd', 0.0) == 0.0:
                    print("⚠️  ПРОБЛЕМА: Инвестировано USD = 0 (должно быть > 0 после покупки)")
                else:
                    print(f"✅ Инвестировано USD: {stats.get('total_invested_usd')}")
                
                if stats.get('start_price', 0.0) == 0.0:
                    print("⚠️  ПРОБЛЕМА: Стартовая цена = 0 (должна быть > 0)")
                else:
                    print(f"✅ Стартовая цена: {stats.get('start_price')}")
                
            else:
                print(f"❌ Запрос завершился с ошибкой: {data.get('error')}")
        else:
            print(f"❌ HTTP ошибка: {resp.status_code}")
            print(resp.text)
    except Exception as e:
        print(f"❌ Исключение: {e}")
    print()
    
    # 3. Проверяем эндпойнт для получения информации о цикле
    print("[3] Информация о цикле ETH (прямой эндпойнт):")
    try:
        resp = requests.get(f"{API_BASE_URL}/api/autotrader/cycle/ETH", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"❌ Ошибка: HTTP {resp.status_code}")
            print(resp.text)
    except Exception as e:
        print(f"❌ Исключение: {e}")
    print()

if __name__ == "__main__":
    diagnose_autotrader_memory()
