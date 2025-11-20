"""
Диагностика автотрейдера: почему не начинается новый цикл
"""
import requests
import json

API_URL = "http://localhost:5000"

def check_autotrader_status():
    """Проверяет состояние автотрейдера"""
    print("=" * 70)
    print("ДИАГНОСТИКА АВТОТРЕЙДЕРА")
    print("=" * 70)
    
    # 1. Проверка состояния автоторговли
    print("\n1. 🔍 Проверка состояния автоторговли...")
    try:
        response = requests.get(f"{API_URL}/api/autotrade/status")
        if response.ok:
            data = response.json()
            print(f"   ✅ Автоторговля включена: {data.get('enabled')}")
        else:
            print(f"   ❌ Ошибка получения статуса: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # 2. Проверка статистики автотрейдера
    print("\n2. 📊 Статистика автотрейдера...")
    try:
        response = requests.get(f"{API_URL}/api/autotrader/stats")
        if response.ok:
            data = response.json()
            print(f"   Всего циклов: {data.get('total_cycles', 0)}")
            print(f"   Активных циклов: {data.get('active_cycles', 0)}")
            print(f"   Покупок: {data.get('total_buy_orders', 0)}")
            print(f"   Продаж: {data.get('total_sell_orders', 0)}")
        else:
            print(f"   ❌ Ошибка получения статистики: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # 3. Проверка разрешений на торговлю
    print("\n3. 🎯 Разрешения на торговлю валют...")
    try:
        response = requests.get(f"{API_URL}/api/trading/permissions")
        if response.ok:
            data = response.json()
            enabled = [k for k, v in data.items() if v]
            disabled = [k for k, v in data.items() if not v]
            print(f"   ✅ Включено ({len(enabled)}): {', '.join(enabled) if enabled else 'нет'}")
            if disabled:
                print(f"   ❌ Выключено ({len(disabled)}): {', '.join(disabled)}")
        else:
            print(f"   ❌ Ошибка получения разрешений: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # 4. Проверка баланса для каждой валюты
    print("\n4. 💰 Проверка балансов валют...")
    try:
        # Получаем список валют
        response = requests.get(f"{API_URL}/api/currencies")
        if response.ok:
            currencies = response.json()
            for curr in currencies[:5]:  # Первые 5 валют
                base = curr.get('code')
                # Получаем баланс
                bal_response = requests.get(f"{API_URL}/api/balance/{base}_USDT")
                if bal_response.ok:
                    bal_data = bal_response.json()
                    base_balance = bal_data.get('base_balance', 0)
                    quote_balance = bal_data.get('quote_balance', 0)
                    print(f"   {base}: {base_balance:.8f} {base} | {quote_balance:.4f} USDT")
                    
                    # Проверяем состояние цикла
                    ind_response = requests.get(f"{API_URL}/api/trade/indicators?base={base}&quote=USDT")
                    if ind_response.ok:
                        ind_data = ind_response.json()
                        if ind_data.get('autotrade_levels'):
                            levels = ind_data['autotrade_levels']
                            active = levels.get('active_cycle', False)
                            step = levels.get('active_step', 'N/A')
                            print(f"      → Цикл активен: {active}, Шаг: {step}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # 5. Проверка параметров breakeven
    print("\n5. ⚙️ Параметры breakeven (первая валюта)...")
    try:
        response = requests.get(f"{API_URL}/api/currencies")
        if response.ok:
            currencies = response.json()
            if currencies:
                base = currencies[0].get('code')
                params_response = requests.get(f"{API_URL}/api/breakeven/params/{base}")
                if params_response.ok:
                    params = params_response.json()
                    print(f"   Валюта: {base}")
                    print(f"   Start volume: {params.get('start_volume', 0)}")
                    print(f"   Keep: {params.get('keep', 0)}")
                    print(f"   Start price: {params.get('start_price', 0)}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    print("\n" + "=" * 70)
    print("ДИАГНОСТИКА ЗАВЕРШЕНА")
    print("=" * 70)

if __name__ == "__main__":
    check_autotrader_status()
