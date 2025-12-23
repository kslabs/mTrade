"""
Тест загрузки параметров через API
Проверяет, возвращаются ли параметры для валюты ETH
"""
import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def test_params_without_currency():
    """Тест загрузки параметров без указания валюты"""
    print("\n" + "="*60)
    print("ТЕСТ 1: Загрузка параметров без указания валюты")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/api/trade/params", timeout=5)
        print(f"Status: {response.status_code}")
        
        if response.ok:
            data = response.json()
            print(f"Success: {data.get('success')}")
            print(f"Params: {json.dumps(data.get('params', {}), indent=2)}")
        else:
            print(f"ERROR: {response.text}")
    except Exception as e:
        print(f"EXCEPTION: {e}")

def test_params_with_eth():
    """Тест загрузки параметров для ETH"""
    print("\n" + "="*60)
    print("ТЕСТ 2: Загрузка параметров для ETH")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/api/trade/params?base_currency=ETH", timeout=5)
        print(f"Status: {response.status_code}")
        
        if response.ok:
            data = response.json()
            print(f"Success: {data.get('success')}")
            print(f"Currency: {data.get('base_currency')}")
            print(f"Params: {json.dumps(data.get('params', {}), indent=2)}")
            
            # Проверка всех ожидаемых полей
            params = data.get('params', {})
            expected_fields = [
                'steps', 'start_volume', 'start_price', 'pprof', 'kprof',
                'target_r', 'rk', 'geom_multiplier', 'rebuy_mode', 'keep', 'orderbook_level'
            ]
            
            print("\nПроверка полей:")
            for field in expected_fields:
                value = params.get(field, 'ОТСУТСТВУЕТ')
                print(f"  - {field}: {value}")
        else:
            print(f"ERROR: {response.text}")
    except Exception as e:
        print(f"EXCEPTION: {e}")

def test_params_with_btc():
    """Тест загрузки параметров для BTC"""
    print("\n" + "="*60)
    print("ТЕСТ 3: Загрузка параметров для BTC")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/api/trade/params?base_currency=BTC", timeout=5)
        print(f"Status: {response.status_code}")
        
        if response.ok:
            data = response.json()
            print(f"Success: {data.get('success')}")
            print(f"Currency: {data.get('base_currency')}")
            print(f"Params: {json.dumps(data.get('params', {}), indent=2)}")
        else:
            print(f"ERROR: {response.text}")
    except Exception as e:
        print(f"EXCEPTION: {e}")

def main():
    print("="*60)
    print("ДИАГНОСТИКА ЗАГРУЗКИ ПАРАМЕТРОВ")
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
    
    # Запуск тестов
    test_params_without_currency()
    test_params_with_eth()
    test_params_with_btc()
    
    print("\n" + "="*60)
    print("ДИАГНОСТИКА ЗАВЕРШЕНА")
    print("="*60)

if __name__ == "__main__":
    main()
