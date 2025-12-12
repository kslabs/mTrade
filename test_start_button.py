"""
Тест кнопки старта цикла
Проверяет API /api/autotrader/resume_cycle
"""
import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def test_resume_cycle(currency='ETH'):
    """Тест старта/возобновления цикла"""
    print("\n" + "="*60)
    print(f"ТЕСТ: Старт цикла для {currency}")
    print("="*60)
    
    try:
        url = f"{BASE_URL}/api/autotrader/resume_cycle"
        payload = {'base_currency': currency}
        
        print(f"URL: {url}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        print("Отправка запроса...")
        
        response = requests.post(url, json=payload, timeout=5)
        print(f"\nStatus: {response.status_code}")
        
        if response.ok:
            data = response.json()
            print(f"Success: {data.get('success')}")
            print(f"Message: {data.get('message')}")
            print(f"Was Paused: {data.get('was_paused')}")
            print(f"New State: {data.get('new_state')}")
            
            if data.get('success'):
                print("\n✅ Цикл успешно запущен!")
            else:
                print(f"\n❌ Ошибка: {data.get('error')}")
        else:
            print(f"❌ HTTP ERROR: {response.text}")
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

def test_cycle_state(currency='ETH'):
    """Проверка состояния цикла"""
    print("\n" + "="*60)
    print(f"ПРОВЕРКА: Состояние цикла для {currency}")
    print("="*60)
    
    try:
        url = f"{BASE_URL}/api/cycle/state?base_currency={currency}"
        print(f"URL: {url}")
        
        response = requests.get(url, timeout=5)
        print(f"Status: {response.status_code}")
        
        if response.ok:
            data = response.json()
            print(f"Success: {data.get('success')}")
            
            if data.get('success'):
                state = data.get('state', {})
                print(f"\nСостояние цикла:")
                print(f"  - Валюта: {state.get('base_currency')}")
                print(f"  - Активен: {state.get('active')}")
                print(f"  - Ручная пауза: {state.get('manual_pause')}")
                print(f"  - Шаг: {state.get('step')}")
                print(f"  - Стартовая цена: {state.get('start_price')}")
            else:
                print(f"❌ Ошибка: {data.get('error')}")
        else:
            print(f"❌ HTTP ERROR: {response.text}")
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")

def test_autotrader_status():
    """Проверка общего статуса автотрейдера"""
    print("\n" + "="*60)
    print("ПРОВЕРКА: Статус автотрейдера")
    print("="*60)
    
    try:
        url = f"{BASE_URL}/api/autotrader/status"
        response = requests.get(url, timeout=5)
        print(f"Status: {response.status_code}")
        
        if response.ok:
            data = response.json()
            print(f"Success: {data.get('success')}")
            
            if data.get('success'):
                print(f"\nАвтотрейдер:")
                print(f"  - Инициализирован: {data.get('initialized')}")
                print(f"  - Глобально включен: {data.get('enabled')}")
                print(f"  - Активных циклов: {data.get('active_cycles')}")
                
                cycles = data.get('cycles', {})
                if cycles:
                    print(f"\nЦиклы:")
                    for currency, cycle_info in cycles.items():
                        print(f"  {currency}:")
                        print(f"    - Активен: {cycle_info.get('active')}")
                        print(f"    - Пауза: {cycle_info.get('manual_pause')}")
                        print(f"    - Шаг: {cycle_info.get('step')}")
            else:
                print(f"❌ Ошибка: {data.get('error')}")
        else:
            print(f"❌ HTTP ERROR: {response.text}")
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")

def main():
    print("="*60)
    print("ДИАГНОСТИКА КНОПКИ СТАРТА ЦИКЛА")
    print("="*60)
    
    # Проверка доступности сервера
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.ok:
            print("✓ Сервер доступен")
        else:
            print("✗ Сервер недоступен")
            return
    except Exception as e:
        print(f"✗ Сервер недоступен: {e}")
        return
    
    # Тесты
    test_autotrader_status()
    test_cycle_state('ETH')
    test_resume_cycle('ETH')
    test_cycle_state('ETH')  # Повторная проверка после старта
    
    print("\n" + "="*60)
    print("ИНСТРУКЦИИ")
    print("="*60)
    print("""
Если цикл успешно запустился, но кнопка на веб-странице не работает:

1. Откройте страницу в браузере: http://127.0.0.1:5000/
2. Откройте консоль (F12)
3. Попробуйте вызвать функцию вручную:
   
   handleResumeCycle()
   
4. Проверьте, есть ли в консоли ошибки
5. Проверьте, что кнопка правильно привязана:
   
   const btn = document.getElementById('resumeCycleBtn');
   console.log('Button:', btn);
   console.log('Click handler:', btn?.onclick);
   
6. Если кнопка не найдена - значит проблема в HTML
7. Если обработчик не привязан - значит проблема в JS инициализации
""")
    
    print("\n" + "="*60)
    print("ДИАГНОСТИКА ЗАВЕРШЕНА")
    print("="*60)

if __name__ == "__main__":
    main()
