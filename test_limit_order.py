"""
Тестовый скрипт для проверки API покупки (лимитный ордер)
"""
from gate_api_client import GateAPIClient
from config import Config

# Загружаем ключи для testnet
api_key, api_secret = Config.load_secrets_by_mode('test')
print(f"[INFO] API Key: {api_key[:10]}...")

# Создаем клиент
client = GateAPIClient(api_key, api_secret, 'test')

# Тестируем создание лимитного ордера
pair = "BTC_USDT"
amount = "0.00004"  # увеличили объем (95000 * 0.00004 = 3.8 USDT > 3 USDT)
price = "95000"  # цена ниже рынка (чтобы не исполнился сразу)

print(f"\n[TEST] Создание лимитного ордера на покупку")
print(f"[TEST] Пара: {pair}, Количество: {amount}, Цена: {price}")

result = client.create_spot_order(
    currency_pair=pair,
    side='buy',
    amount=amount,
    price=price,
    order_type='limit'
)

print(f"\n[RESULT] Ответ API:")
print(f"  Type: {type(result)}")
print(f"  Content: {result}")
print(f"  Has 'label': {'label' in result if isinstance(result, dict) else 'N/A'}")
print(f"  Has 'id': {'id' in result if isinstance(result, dict) else 'N/A'}")

if isinstance(result, dict) and 'id' in result:
    print(f"\n✅ Ордер создан успешно! Order ID: {result['id']}")
else:
    print(f"\n❌ Ошибка создания ордера")
