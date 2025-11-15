"""
Тестовый скрипт для проверки API покупки
"""
from gate_api_client import GateAPIClient
from config import Config

# Загружаем ключи для testnet
api_key, api_secret = Config.load_secrets_by_mode('test')
print(f"[INFO] API Key: {api_key[:10]}...")

# Создаем клиент
client = GateAPIClient(api_key, api_secret, 'test')

# Тестируем создание рыночного ордера
pair = "BTC_USDT"
amount = "0.00004"  # увеличенный объем

print(f"\n[TEST] Создание рыночного ордера на покупку")
print(f"[TEST] Пара: {pair}, Количество: {amount}")

result = client.create_spot_order(
    currency_pair=pair,
    side='buy',
    amount=amount,
    order_type='market'
)

print(f"\n[RESULT] Ответ API:")
print(f"  Type: {type(result)}")
print(f"  Content: {result}")
print(f"  Has 'label': {'label' in result if isinstance(result, dict) else 'N/A'}")
print(f"  Has 'id': {'id' in result if isinstance(result, dict) else 'N/A'}")
