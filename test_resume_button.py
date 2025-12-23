"""
Тест кнопки старта цикла - проверка всех компонентов
"""
import requests
import json

BASE_URL = "http://localhost:5000"

def test_resume_cycle(base_currency="ETH"):
    """Тестирование API возобновления цикла"""
    print(f"\n{'='*60}")
    print(f"ТЕСТ КНОПКИ СТАРТА ЦИКЛА ДЛЯ {base_currency}")
    print(f"{'='*60}\n")
    
    # 1. Проверяем текущее состояние
    print("1. Проверяем текущее состояние цикла...")
    try:
        response = requests.get(f"{BASE_URL}/api/autotrader/indicators?base_currency={base_currency}")
        if response.ok:
            data = response.json()
            print(f"   ✓ Состояние получено:")
            print(f"     - Цикл активен: {data.get('cycle_active', 'N/A')}")
            print(f"     - Ручная пауза: {data.get('manual_pause', 'N/A')}")
            print(f"     - Текущий шаг: {data.get('current_step', 'N/A')}")
        else:
            print(f"   ✗ Ошибка получения состояния: {response.status_code}")
    except Exception as e:
        print(f"   ✗ Исключение: {e}")
    
    # 2. Отправляем запрос на возобновление цикла
    print(f"\n2. Отправляем запрос на старт цикла...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/autotrader/resume_cycle",
            json={"base_currency": base_currency},
            headers={"Content-Type": "application/json"}
        )
        
        print(f"   Статус ответа: {response.status_code}")
        
        if response.ok:
            data = response.json()
            print(f"   ✓ Ответ сервера:")
            print(f"     - Success: {data.get('success')}")
            print(f"     - Message: {data.get('message')}")
            print(f"     - Was paused: {data.get('was_paused')}")
            print(f"     - New state: {data.get('new_state')}")
        else:
            print(f"   ✗ Ошибка: {response.status_code}")
            print(f"     Текст: {response.text}")
            
    except Exception as e:
        print(f"   ✗ Исключение: {e}")
    
    # 3. Проверяем состояние после возобновления
    print(f"\n3. Проверяем состояние после старта...")
    try:
        response = requests.get(f"{BASE_URL}/api/autotrader/indicators?base_currency={base_currency}")
        if response.ok:
            data = response.json()
            print(f"   ✓ Новое состояние:")
            print(f"     - Цикл активен: {data.get('cycle_active', 'N/A')}")
            print(f"     - Ручная пауза: {data.get('manual_pause', 'N/A')}")
            print(f"     - Текущий шаг: {data.get('current_step', 'N/A')}")
        else:
            print(f"   ✗ Ошибка получения состояния: {response.status_code}")
    except Exception as e:
        print(f"   ✗ Исключение: {e}")
    
    # 4. Проверяем файл состояния
    print(f"\n4. Проверяем файл состояния...")
    try:
        with open("autotrader_cycles_state.json", "r", encoding="utf-8") as f:
            state = json.load(f)
            if base_currency in state:
                cycle = state[base_currency]
                print(f"   ✓ Состояние в файле:")
                print(f"     - Цикл активен: {cycle.get('cycle_active', 'N/A')}")
                print(f"     - Ручная пауза: {cycle.get('manual_pause', 'N/A')}")
                print(f"     - Текущий шаг: {cycle.get('current_step', 'N/A')}")
            else:
                print(f"   ✗ Валюта {base_currency} не найдена в файле состояния")
    except Exception as e:
        print(f"   ✗ Ошибка чтения файла: {e}")
    
    print(f"\n{'='*60}")
    print("ТЕСТ ЗАВЕРШЁН")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    import sys
    currency = sys.argv[1] if len(sys.argv) > 1 else "ETH"
    test_resume_cycle(currency)
