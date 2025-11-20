"""
Тестовый скрипт для диагностики торговли DOGE
Проверяет все шаги процесса закупки DOGE
"""

import json
import sys
from gate_api_client import GateAPIClient

def main():
    print("=" * 70)
    print("ДИАГНОСТИКА ТОРГОВЛИ DOGE")
    print("=" * 70)
    
    # 1. Проверка конфигурации
    print("\n1️⃣ ПРОВЕРКА КОНФИГУРАЦИИ")
    print("-" * 70)
    
    try:
        with open('app_state.json', 'r', encoding='utf-8') as f:
            app_state = json.load(f)
        
        auto_trade = app_state.get('auto_trade_enabled', False)
        perms = app_state.get('trading_permissions', {})
        params = app_state.get('breakeven_params', {})
        network_mode = app_state.get('network_mode', 'work')
        quote = app_state.get('active_quote_currency', 'USDT')
        
        print(f"✅ Автоторговля: {auto_trade}")
        print(f"✅ Режим сети: {network_mode}")
        print(f"✅ Котировочная валюта: {quote}")
        print(f"✅ DOGE разрешена: {perms.get('DOGE', False)}")
        
        if 'DOGE' in params:
            doge_params = params['DOGE']
            print(f"✅ Параметры DOGE найдены:")
            print(f"   start_volume: {doge_params.get('start_volume')}")
            print(f"   start_price: {doge_params.get('start_price')}")
            print(f"   steps: {doge_params.get('steps')}")
        else:
            print(f"❌ Параметры DOGE не найдены!")
            return
            
    except Exception as e:
        print(f"❌ Ошибка чтения app_state.json: {e}")
        return
    
    # 2. Проверка подключения к API
    print("\n2️⃣ ПРОВЕРКА API")
    print("-" * 70)
    
    try:
        with open('accounts.json', 'r', encoding='utf-8') as f:
            accounts = json.load(f)
        
        # Находим любой аккаунт (приоритет Auto_test)
        test_account = accounts.get('Auto_test') or accounts.get('test')
        if not test_account:
            # Берём первый доступный
            if accounts:
                test_account = list(accounts.values())[0]
                print(f"ℹ️ Используется первый доступный аккаунт")
            else:
                print("❌ Ни один аккаунт не найден!")
                return
        
        api_key = test_account.get('api_key')
        api_secret = test_account.get('api_secret')
        
        if not api_key or not api_secret:
            print("❌ API ключи не настроены!")
            return
        
        print(f"✅ API ключи найдены (key: {api_key[:8]}...)")
        
        # Создаём клиент
        client = GateAPIClient(api_key=api_key, api_secret=api_secret, network_mode='test')
        print(f"✅ API клиент создан (режим: test)")
        
    except Exception as e:
        print(f"❌ Ошибка настройки API: {e}")
        return
    
    # 3. Проверка баланса
    print("\n3️⃣ ПРОВЕРКА БАЛАНСА")
    print("-" * 70)
    
    try:
        balance = client.get_account_balance()
        if not isinstance(balance, list):
            print(f"❌ Неверный формат баланса: {type(balance)}")
            return
        
        usdt_balance = 0.0
        doge_balance = 0.0
        
        for item in balance:
            currency = item.get('currency', '').upper()
            available = float(item.get('available', 0))
            
            if currency == 'USDT':
                usdt_balance = available
            elif currency == 'DOGE':
                doge_balance = available
        
        print(f"💰 Баланс USDT: {usdt_balance:.4f}")
        print(f"💰 Баланс DOGE: {doge_balance:.8f}")
        
        start_volume = doge_params.get('start_volume', 10.0)
        if usdt_balance < start_volume:
            print(f"⚠️ ВНИМАНИЕ: Недостаточно USDT!")
            print(f"   Требуется: {start_volume:.4f} USDT")
            print(f"   Доступно: {usdt_balance:.4f} USDT")
            print(f"   💡 Пополните баланс или уменьшите start_volume")
        else:
            print(f"✅ USDT достаточно для торговли")
            
    except Exception as e:
        print(f"❌ Ошибка получения баланса: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 4. Проверка получения цены
    print("\n4️⃣ ПРОВЕРКА ЦЕНЫ DOGE")
    print("-" * 70)
    
    try:
        # Пробуем получить цену через публичный API
        public_client = GateAPIClient(api_key=None, api_secret=None, network_mode='work')
        pair = 'DOGE_USDT'
        
        tick = public_client._request('GET', '/spot/tickers', params={'currency_pair': pair})
        
        if isinstance(tick, list) and tick:
            last_price = float(tick[0].get('last', 0))
            bid = float(tick[0].get('highest_bid', 0))
            ask = float(tick[0].get('lowest_ask', 0))
            volume = float(tick[0].get('base_volume', 0))
            
            print(f"✅ Цена получена:")
            print(f"   Последняя: {last_price:.8f} USDT")
            print(f"   Bid: {bid:.8f} USDT")
            print(f"   Ask: {ask:.8f} USDT")
            print(f"   Объём 24ч: {volume:.2f} DOGE")
        else:
            print(f"❌ Не удалось получить цену!")
            return
            
    except Exception as e:
        print(f"❌ Ошибка получения цены: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 5. Проверка минимальных требований
    print("\n5️⃣ ПРОВЕРКА МИНИМАЛЬНЫХ ОБЪЁМОВ")
    print("-" * 70)
    
    try:
        # Получаем детали пары
        pair_details = public_client.get_currency_pair_details_exact('DOGE_USDT')
        
        if isinstance(pair_details, dict):
            min_quote = float(pair_details.get('min_quote_amount', 0))
            min_base = float(pair_details.get('min_base_amount', 0))
            
            print(f"✅ Минимальные требования пары:")
            print(f"   min_quote_amount: {min_quote:.4f} USDT")
            print(f"   min_base_amount: {min_base:.8f} DOGE")
            
            # Проверяем объём покупки
            purchase_amount = start_volume
            doge_amount = purchase_amount / last_price
            
            print(f"\n💡 Планируемая покупка:")
            print(f"   Объём: {purchase_amount:.4f} USDT")
            print(f"   Количество: {doge_amount:.8f} DOGE")
            
            if purchase_amount < min_quote:
                print(f"   ⚠️ Объём меньше минимального! Будет увеличен до {min_quote:.4f} USDT")
            else:
                print(f"   ✅ Объём соответствует минимальному")
                
            if doge_amount < min_base:
                print(f"   ⚠️ Количество меньше минимального! Будет увеличено до {min_base:.8f} DOGE")
            else:
                print(f"   ✅ Количество соответствует минимальному")
        else:
            print(f"⚠️ Не удалось получить детали пары")
            
    except Exception as e:
        print(f"❌ Ошибка получения деталей пары: {e}")
        import traceback
        traceback.print_exc()
    
    # 6. Итоговая диагностика
    print("\n" + "=" * 70)
    print("📊 ИТОГОВАЯ ДИАГНОСТИКА")
    print("=" * 70)
    
    issues = []
    
    if not auto_trade:
        issues.append("❌ Автоторговля отключена")
    
    if not perms.get('DOGE', False):
        issues.append("❌ DOGE не имеет разрешения на торговлю")
    
    if usdt_balance < start_volume:
        issues.append(f"❌ Недостаточно USDT (нужно {start_volume:.4f}, есть {usdt_balance:.4f})")
    
    if not issues:
        print("✅ ВСЁ В ПОРЯДКЕ! Автотрейдер должен торговать DOGE")
        print("\n💡 Если торговля не начинается:")
        print("   1. Убедитесь, что приложение запущено: python mTrade.py")
        print("   2. Проверьте логи приложения на наличие ошибок")
        print("   3. Убедитесь, что WebSocket подключение работает")
    else:
        print("⚠️ НАЙДЕНЫ ПРОБЛЕМЫ:")
        for issue in issues:
            print(f"   {issue}")
        print("\n💡 Исправьте указанные проблемы для начала торговли")
    
    print("=" * 70)

if __name__ == '__main__':
    main()
