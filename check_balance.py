import requests

response = requests.get('http://localhost:5000/api/balance/DOGE_USDT')
if response.ok:
    data = response.json()
    print(f"DOGE баланс: {data.get('base_balance', 'N/A')}")
    print(f"USDT баланс: {data.get('quote_balance', 'N/A')}")
else:
    print(f"Ошибка: {response.status_code}")
