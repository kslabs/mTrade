"""Скрипт для ручной продажи ETH через MARKET ордер"""
import requests
import json

# Продаём ETH через MARKET ордер
url = "http://localhost:5000/api/trade/sell-all"
data = {
    "base_currency": "ETH",
    "quote_currency": "USDT"
}

response = requests.post(url, json=data)
print("Статус:", response.status_code)
print("Ответ:", json.dumps(response.json(), indent=2, ensure_ascii=False))

# Отменяем лимитный ордер, если создался
if response.json().get("success") and response.json().get("order", {}).get("type") == "limit":
    order_id = response.json()["order_id"]
    print(f"\n⚠️ Создался лимитный ордер {order_id}, отменяем его...")
    
    # Отменяем через API Gate.io
    from config import Config
    from gate_api_client import GateAPIClient
    
    api_key, api_secret = Config.load_secrets_by_mode("test")
    api_client = GateAPIClient(api_key, api_secret, "test")
    
    try:
        cancel_result = api_client.cancel_spot_order(order_id, "ETH_USDT")
        print(f"✅ Ордер отменён: {cancel_result}")
    except Exception as e:
        print(f"❌ Ошибка отмены: {e}")
    
    # Создаём MARKET ордер вручную
    print("\n🔥 Создаём MARKET ордер...")
    try:
        market_order = api_client.create_spot_order({
            "currency_pair": "ETH_USDT",
            "side": "sell",
            "amount": "0.0064",
            "type": "market",
            "account": "spot",
            "time_in_force": "ioc"
        })
        print(f"✅ MARKET ордер создан: {json.dumps(market_order, indent=2)}")
    except Exception as e:
        print(f"❌ Ошибка создания MARKET ордера: {e}")
