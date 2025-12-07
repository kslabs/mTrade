"""
Детальная диагностика API индикаторов
"""
import requests
import traceback

BASE_URL = "http://localhost:5000"

def test_indicators_api(base_currency="ETH"):
    """Тестирование API индикаторов"""
    print(f"\n{'='*60}")
    print(f"ТЕСТ API ИНДИКАТОРОВ ДЛЯ {base_currency}")
    print(f"{'='*60}\n")
    
    try:
        url = f"{BASE_URL}/api/trade/indicators?base_currency={base_currency}&quote_currency=USDT"
        print(f"URL: {url}")
        
        response = requests.get(url)
        
        print(f"\nСтатус: {response.status_code}")
        print(f"Заголовки ответа: {dict(response.headers)}")
        
        if response.ok:
            data = response.json()
            print(f"\n✓ Данные получены успешно:")
            print(f"  - Success: {data.get('success')}")
            print(f"  - Indicators: {data.get('indicators', {}).get('pair')}")
            print(f"  - Autotrade levels: {data.get('autotrade_levels', {}).get('active_cycle')}")
        else:
            print(f"\n✗ Ошибка {response.status_code}:")
            print(f"  Текст ответа:\n{response.text}")
            
    except Exception as e:
        print(f"\n✗ Исключение:")
        print(traceback.format_exc())

if __name__ == "__main__":
    import sys
    currency = sys.argv[1] if len(sys.argv) > 1 else "ETH"
    test_indicators_api(currency)
