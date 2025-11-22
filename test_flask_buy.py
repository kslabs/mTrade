"""
Полный тест покупки через Flask API
"""
import requests
import json

url = 'http://localhost:5000/api/trade/buy-min'
data = {
    'base_currency': 'BTC',
    'quote_currency': 'USDT'
}

print(f"[TEST] Отправка POST запроса на {url}")
print(f"[TEST] Данные: {data}")

response = requests.post(url, json=data)

print(f"\n[RESPONSE] Status: {response.status_code}")
print(f"[RESPONSE] Headers: {dict(response.headers)}")
print(f"\n[RESPONSE] Body:")
result = response.json()
print(json.dumps(result, indent=2, ensure_ascii=False))

if result.get('success'):
    print(f"\n✅ Успешно!")
    print(f"Order ID: {result.get('order_id', 'unknown')}")
else:
    print(f"\n❌ Ошибка: {result.get('error', 'unknown')}")
