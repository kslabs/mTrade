"""
Тестовый скрипт для диагностики ошибки при покупке минимального ордера
"""
import sys
import traceback
from config import Config
from gate_api_client import GateAPIClient

def test_buy_min():
    """Эмулирует логику эндпоинта /api/trade/buy-min"""
    try:
        # Параметры для теста
        base_currency = "BTC"
        quote_currency = "USDT"
        pair = f"{base_currency}_{quote_currency}"
        
        # Определяем текущий режим (обычно из конфига или переменной окружения)
        CURRENT_NETWORK_MODE = "testnet"  # или "mainnet"
        
        print(f"[INFO] Тест покупки минимального ордера для пары: {pair}")
        print(f"[INFO] Режим сети: {CURRENT_NETWORK_MODE}")
        
        # Получаем API ключи
        print("\n[STEP 1] Загрузка API ключей...")
        api_key, api_secret = Config.load_secrets_by_mode(CURRENT_NETWORK_MODE)
        
        if not api_key or not api_secret:
            print("[ERROR] API ключи не найдены!")
            return False
        
        print(f"[OK] API ключ загружен: {api_key[:10]}...")
        
        # Создаём клиент API
        print("\n[STEP 2] Создание API клиента...")
        api_client = GateAPIClient(api_key, api_secret, CURRENT_NETWORK_MODE)
        print("[OK] API клиент создан")
        
        # Получаем параметры пары
        print(f"\n[STEP 3] Получение параметров пары {pair}...")
        pair_info = api_client.get_currency_pair_details_exact(pair)
        
        if not pair_info or 'error' in pair_info:
            print(f"[ERROR] Пара {pair} не найдена или ошибка: {pair_info}")
            return False
        
        print(f"[OK] Параметры пары получены:")
        print(f"  - min_quote_amount: {pair_info.get('min_quote_amount', 'N/A')}")
        print(f"  - amount_precision: {pair_info.get('amount_precision', 'N/A')}")
        print(f"  - precision: {pair_info.get('precision', 'N/A')}")
        
        # Для теста используем фиктивную цену (в реальном коде берётся из WebSocket)
        print("\n[STEP 4] Расчёт параметров ордера...")
        best_ask = 50000.0  # Примерная цена BTC/USDT
        min_quote = float(pair_info.get('min_quote_amount', '5'))
        
        print(f"  - Лучшая цена ask: {best_ask}")
        print(f"  - Минимальная сумма: {min_quote}")
        
        # Рассчитываем количество
        amount = min_quote / best_ask
        amount_precision = int(pair_info.get('amount_precision', 8))
        amount = round(amount, amount_precision)
        
        # Форматируем без научной нотации
        amount_str = f"{amount:.{amount_precision}f}"
        
        print(f"  - Рассчитанное количество (raw): {amount}")
        print(f"  - Рассчитанное количество (formatted): {amount_str}")
        print(f"  - Точность количества: {amount_precision}")
        
        # Проверяем минимальное количество (если есть)
        if 'min_base_amount' in pair_info:
            min_base = float(pair_info['min_base_amount'])
            if amount < min_base:
                print(f"[WARNING] Количество {amount} меньше минимального {min_base}")
                amount = min_base
                print(f"[INFO] Скорректировано до минимального: {amount}")
        
        print(f"\n[STEP 5] Создание тестового ордера...")
        print(f"  Параметры ордера:")
        print(f"  - currency_pair: {pair}")
        print(f"  - side: buy")
        print(f"  - amount: {amount_str}")
        print(f"  - order_type: market")
        
        print(f"\n[INFO] ✅ ИСПРАВЛЕНО: Количество форматируется БЕЗ научной нотации!")
        print(f"  - Старый формат (неправильно): {str(amount)}")
        print(f"  - Новый формат (правильно): {amount_str}")
        
        # В тестовом режиме НЕ создаём реальный ордер, только показываем параметры
        print("\n[INFO] Это тестовый режим - реальный ордер не создаётся")
        print("[INFO] Для создания реального ордера раскомментируйте следующий блок:")
        print("""
        result = api_client.create_spot_order(
            currency_pair=pair,
            side='buy',
            amount=str(amount),
            order_type='market'
        )
        print(f"[OK] Ордер создан: {result}")
        """)
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Произошла ошибка: {e}")
        print("\n[TRACEBACK]")
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("=" * 80)
    print("ТЕСТ ПОКУПКИ МИНИМАЛЬНОГО ОРДЕРА")
    print("=" * 80)
    
    success = test_buy_min()
    
    print("\n" + "=" * 80)
    if success:
        print("ТЕСТ ПРОЙДЕН УСПЕШНО")
    else:
        print("ТЕСТ ПРОВАЛЕН")
    print("=" * 80)
