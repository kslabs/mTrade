"""
Расширенный тестовый скрипт для проверки покупки минимального ордера
Включает реальное создание ордера в тестовой сети
"""
import sys
import traceback
from config import Config
from gate_api_client import GateAPIClient

def test_buy_min_real():
    """Эмулирует логику эндпоинта /api/trade/buy-min с реальным созданием ордера"""
    try:
        # Параметры для теста
        base_currency = "BTC"
        quote_currency = "USDT"
        pair = f"{base_currency}_{quote_currency}"
        
        # ВАЖНО: Используем TESTNET для безопасности!
        CURRENT_NETWORK_MODE = "testnet"
        
        print(f"[INFO] Тест покупки минимального ордера для пары: {pair}")
        print(f"[INFO] Режим сети: {CURRENT_NETWORK_MODE}")
        print(f"[WARNING] Это реальный тест с созданием ордера в тестовой сети!")
        
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
        print(f"  - min_base_amount: {pair_info.get('min_base_amount', 'N/A')}")
        
        # Получаем текущий тикер для реальной цены
        print("\n[STEP 4] Получение текущей цены...")
        ticker = api_client.get_ticker(pair)
        
        if not ticker or 'error' in ticker:
            print(f"[ERROR] Не удалось получить тикер: {ticker}")
            return False
        
        # Используем lowest_ask как best_ask
        best_ask = float(ticker.get('lowest_ask', '0'))
        if best_ask == 0:
            print("[ERROR] Цена ask равна 0!")
            return False
        
        print(f"[OK] Текущая цена ask: {best_ask}")
        
        # Расчёт параметров ордера
        print("\n[STEP 5] Расчёт параметров ордера...")
        min_quote = float(pair_info.get('min_quote_amount', '5'))
        
        print(f"  - Лучшая цена ask: {best_ask}")
        print(f"  - Минимальная сумма: {min_quote}")
        
        # Рассчитываем количество
        amount = min_quote / best_ask
        amount_precision = int(pair_info.get('amount_precision', 8))
        amount = round(amount, amount_precision)
        
        print(f"  - Рассчитанное количество (до округления): {amount}")
        print(f"  - Точность количества: {amount_precision}")
        
        # Форматируем без научной нотации
        amount_str = f"{amount:.{amount_precision}f}"
        print(f"  - Форматированное количество: {amount_str}")
        
        # Проверяем минимальное количество
        if 'min_base_amount' in pair_info:
            min_base = float(pair_info['min_base_amount'])
            if amount < min_base:
                print(f"[WARNING] Количество {amount} меньше минимального {min_base}")
                amount = min_base
                amount_str = f"{amount:.{amount_precision}f}"
                print(f"[INFO] Скорректировано до минимального: {amount_str}")
        
        # Проверяем баланс перед созданием ордера
        print("\n[STEP 6] Проверка баланса...")
        balance = api_client.get_account_balance()
        
        usdt_balance = 0
        for item in balance:
            if item.get('currency', '').upper() == 'USDT':
                usdt_balance = float(item.get('available', '0'))
                break
        
        print(f"[INFO] Доступный баланс USDT: {usdt_balance}")
        
        if usdt_balance < min_quote:
            print(f"[ERROR] Недостаточно USDT! Требуется {min_quote}, доступно {usdt_balance}")
            return False
        
        print(f"\n[STEP 7] Создание РЕАЛЬНОГО market ордера на покупку...")
        print(f"  Параметры ордера:")
        print(f"  - currency_pair: {pair}")
        print(f"  - side: buy")
        print(f"  - amount: {amount_str}")
        print(f"  - order_type: market")
        
        # Создаём реальный ордер
        result = api_client.create_spot_order(
            currency_pair=pair,
            side='buy',
            amount=amount_str,
            order_type='market'
        )
        
        print(f"\n[INFO] Ответ API:")
        print(f"{result}")
        
        # Проверяем результат
        if isinstance(result, dict):
            if 'id' in result:
                print(f"\n[SUCCESS] Ордер успешно создан!")
                print(f"  - Order ID: {result['id']}")
                print(f"  - Status: {result.get('status', 'N/A')}")
                print(f"  - Amount: {result.get('amount', 'N/A')}")
                print(f"  - Price: {result.get('price', 'N/A')}")
                return True
            elif 'label' in result:
                print(f"\n[ERROR] Ошибка API:")
                print(f"  - Label: {result.get('label')}")
                print(f"  - Message: {result.get('message')}")
                return False
        
        print(f"[WARNING] Неожиданный формат ответа")
        return False
        
    except Exception as e:
        print(f"\n[ERROR] Произошла ошибка: {e}")
        print("\n[TRACEBACK]")
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("=" * 80)
    print("РЕАЛЬНЫЙ ТЕСТ ПОКУПКИ МИНИМАЛЬНОГО ОРДЕРА")
    print("=" * 80)
    print("\nВНИМАНИЕ: Этот скрипт создаст реальный ордер в TESTNET!")
    print("Убедитесь, что у вас есть тестовый баланс USDT.\n")
    
    response = input("Продолжить? (yes/no): ")
    if response.lower() != 'yes':
        print("Тест отменён пользователем.")
        sys.exit(0)
    
    print("\n" + "=" * 80)
    success = test_buy_min_real()
    
    print("\n" + "=" * 80)
    if success:
        print("ТЕСТ ПРОЙДЕН УСПЕШНО - ОРДЕР СОЗДАН!")
    else:
        print("ТЕСТ ПРОВАЛЕН - ОРДЕР НЕ СОЗДАН")
    print("=" * 80)
