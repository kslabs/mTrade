import requests

# Тестовая сеть Gate.io
test_api = "https://api-testnet.gateio.ws/api/v4"

print("=== Проверка тестовой сети Gate.io ===\n")

# Проверка доступности тестового API
try:
    # Получение тикера
    ticker_url = f"{test_api}/spot/tickers?currency_pair=BTC_USDT"
    print(f"1. Проверка тикера: {ticker_url}")
    r = requests.get(ticker_url, timeout=5)
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"   Response: {data}")
    else:
        print(f"   Error: {r.text}")
    
    print()
    
    # Получение стакана
    orderbook_url = f"{test_api}/spot/order_book?currency_pair=BTC_USDT&limit=20"
    print(f"2. Проверка стакана: {orderbook_url}")
    r = requests.get(orderbook_url, timeout=5)
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"   Asks count: {len(data.get('asks', []))}")
        print(f"   Bids count: {len(data.get('bids', []))}")
        if data.get('asks'):
            print(f"   First ask: {data['asks'][0]}")
        if data.get('bids'):
            print(f"   First bid: {data['bids'][0]}")
    else:
        print(f"   Error: {r.text}")
        
except Exception as e:
    print(f"Exception: {e}")

print("\n=== Проверка рабочей сети Gate.io ===\n")

# Рабочая сеть Gate.io для сравнения
work_api = "https://api.gateio.ws/api/v4"

try:
    orderbook_url = f"{work_api}/spot/order_book?currency_pair=BTC_USDT&limit=20"
    print(f"Проверка стакана: {orderbook_url}")
    r = requests.get(orderbook_url, timeout=5)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Asks count: {len(data.get('asks', []))}")
        print(f"Bids count: {len(data.get('bids', []))}")
        if data.get('asks'):
            print(f"First ask: {data['asks'][0]}")
except Exception as e:
    print(f"Exception: {e}")
