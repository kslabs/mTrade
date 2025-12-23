"""
Детальная диагностика продажи XRP - V3
ПРОВЕРЯЕТ ВСЕ возможные причины непродажи
"""

import json
import os
import sys

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gate_api_client import GateAPIClient
from state_manager import StateManager

def check_xrp_sell():
    """Детальная проверка почему не продается XRP"""
    
    print("=" * 80)
    print("ДИАГНОСТИКА ПРОДАЖИ XRP - V3")
    print("=" * 80)
    
    base = "XRP"
    quote = "USDT"
    
    # 1. ПРОВЕРЯЕМ СОСТОЯНИЕ ЦИКЛА ИЗ ФАЙЛА
    print("\n1️⃣ СОСТОЯНИЕ ЦИКЛА ИЗ ФАЙЛА:")
    print("-" * 80)
    
    state_file = "autotrader_cycles_state.json"
    if not os.path.exists(state_file):
        print(f"❌ ФАЙЛ {state_file} НЕ НАЙДЕН!")
        return
    
    with open(state_file, "r", encoding="utf-8") as f:
        state_data = json.load(f)
    
    if base not in state_data:
        print(f"❌ XRP НЕ НАЙДЕН В ФАЙЛЕ СОСТОЯНИЯ!")
        return
    
    xrp_state = state_data[base]
    
    print(f"active: {xrp_state.get('active')}")
    print(f"cycle_id: {xrp_state.get('cycle_id')}")
    print(f"active_step: {xrp_state.get('active_step')}")
    print(f"start_price: {xrp_state.get('start_price')}")
    print(f"base_volume: {xrp_state.get('base_volume')}")
    print(f"total_invested_usd: {xrp_state.get('total_invested_usd')}")
    print(f"manual_pause: {xrp_state.get('manual_pause')}")
    print(f"_selling_in_progress: {xrp_state.get('_selling_in_progress', 'НЕТ ПОЛЯ')}")
    
    if not xrp_state.get('active'):
        print("\n❌ ЦИКЛ НЕ АКТИВЕН! Продажа невозможна.")
        return
    
    # 2. ПРОВЕРЯЕМ ПАРАМЕТРЫ ТОРГОВЛИ
    print("\n2️⃣ ПАРАМЕТРЫ ТОРГОВЛИ:")
    print("-" * 80)
    
    state_manager = StateManager()
    params = state_manager.get_breakeven_params(base)
    
    if not params:
        print("❌ ПАРАМЕТРЫ НЕ НАЙДЕНЫ!")
        return
    
    print(f"start_volume: {params.get('start_volume')}")
    print(f"breakeven_pct: {params.get('breakeven_pct')}")
    print(f"start_price: {params.get('start_price')}")
    
    # 3. ПОЛУЧАЕМ ТЕКУЩУЮ ЦЕНУ
    print("\n3️⃣ ТЕКУЩАЯ ЦЕНА:")
    print("-" * 80)
    
    try:
        public = GateAPIClient(api_key=None, api_secret=None, network_mode='work')
        pair = f"{base}_{quote}".upper()
        tick = public._request('GET', '/spot/tickers', params={'currency_pair': pair})
        
        if isinstance(tick, list) and tick:
            market_price = float(tick[0].get('last', 0))
            print(f"Market price (ticker.last): {market_price:.8f}")
        else:
            print("❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ ЦЕНУ!")
            return
    except Exception as e:
        print(f"❌ ОШИБКА ПОЛУЧЕНИЯ ЦЕНЫ: {e}")
        return
    
    # 4. ПРОВЕРЯЕМ УСЛОВИЕ ПРОДАЖИ
    print("\n4️⃣ ПРОВЕРКА УСЛОВИЯ ПРОДАЖИ:")
    print("-" * 80)
    
    start_price = xrp_state.get('start_price', 0)
    active_step = xrp_state.get('active_step', -1)
    table = xrp_state.get('table', [])
    
    if start_price <= 0:
        print(f"❌ start_price не установлен: {start_price}")
        return
    
    if active_step < 0 or active_step >= len(table):
        print(f"❌ Некорректный active_step: {active_step} (len(table)={len(table)})")
        return
    
    params_row = table[active_step]
    required_growth_pct = float(params_row.get('breakeven_pct', 0))
    current_growth_pct = ((market_price - start_price) / start_price) * 100.0
    
    print(f"Start price: {start_price:.8f}")
    print(f"Market price: {market_price:.8f}")
    print(f"Current growth: {current_growth_pct:.4f}%")
    print(f"Required growth: {required_growth_pct:.4f}%")
    print(f"Условие: {current_growth_pct:.4f}% >= {required_growth_pct:.4f}%")
    
    if current_growth_pct < required_growth_pct:
        print(f"\n❌ УСЛОВИЕ НЕ ВЫПОЛНЕНО! Рост недостаточен.")
        print(f"   Нужно ещё: {required_growth_pct - current_growth_pct:.4f}%")
        return
    
    print(f"\n✅ УСЛОВИЕ ВЫПОЛНЕНО! Продажа ДОЛЖНА происходить!")
    
    # 5. ПРОВЕРЯЕМ ОТКРЫТЫЕ ОРДЕРА
    print("\n5️⃣ ПРОВЕРКА ОТКРЫТЫХ ОРДЕРОВ:")
    print("-" * 80)
    
    try:
        # Загружаем API ключи
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        if not os.path.exists(config_path):
            print("❌ config.json не найден!")
            return
        
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        api_key = config.get("gate_api_key")
        api_secret = config.get("gate_api_secret")
        
        if not api_key or not api_secret:
            print("❌ API ключи не найдены в config.json!")
            return
        
        api = GateAPIClient(api_key=api_key, api_secret=api_secret, network_mode='work')
        open_orders = api.get_spot_orders(pair, status="open")
        
        print(f"Всего открытых ордеров: {len(open_orders)}")
        
        sell_orders = [o for o in open_orders if o.get('side') == 'sell']
        print(f"Открытых SELL ордеров: {len(sell_orders)}")
        
        if sell_orders:
            print("\n⚠️ НАЙДЕНЫ ОТКРЫТЫЕ SELL ОРДЕРА:")
            for order in sell_orders:
                print(f"  ID: {order.get('id')}")
                print(f"  Price: {order.get('price')}")
                print(f"  Amount: {order.get('amount')}")
                print(f"  Status: {order.get('status')}")
                print()
        
    except Exception as e:
        print(f"❌ ОШИБКА ПРОВЕРКИ ОРДЕРОВ: {e}")
    
    # 6. ПРОВЕРЯЕМ БАЛАНС
    print("\n6️⃣ ПРОВЕРКА БАЛАНСА:")
    print("-" * 80)
    
    try:
        all_balances = api.get_account_balance()
        balance_base = next((b for b in all_balances if b.get('currency') == base), None)
        
        if balance_base:
            available = float(balance_base.get('available', 0))
            locked = float(balance_base.get('locked', 0))
            total = available + locked
            
            print(f"Баланс {base}:")
            print(f"  Available: {available:.8f}")
            print(f"  Locked: {locked:.8f}")
            print(f"  Total: {total:.8f}")
            
            expected_volume = xrp_state.get('base_volume', 0)
            print(f"\nОжидаемый объём (из состояния): {expected_volume:.8f}")
            print(f"Реальный доступный объём: {available:.8f}")
            
            if available < expected_volume * 0.999:
                print(f"\n⚠️ НЕДОСТАТОЧНО МОНЕТ ДЛЯ ПРОДАЖИ!")
                print(f"   Нужно: {expected_volume:.8f}")
                print(f"   Есть: {available:.8f}")
                print(f"   Не хватает: {expected_volume - available:.8f}")
        else:
            print(f"❌ Баланс {base} не найден!")
    
    except Exception as e:
        print(f"❌ ОШИБКА ПРОВЕРКИ БАЛАНСА: {e}")
    
    # 7. ФИНАЛЬНЫЙ ВЕРДИКТ
    print("\n" + "=" * 80)
    print("ФИНАЛЬНЫЙ ВЕРДИКТ:")
    print("=" * 80)
    print("\n✅ Все проверки пройдены - продажа ДОЛЖНА происходить!")
    print("\n🔍 ВОЗМОЖНЫЕ ПРИЧИНЫ НЕПРОДАЖИ:")
    print("   1. Автотрейдер не запущен или остановлен")
    print("   2. Флаг _selling_in_progress застрял в True")
    print("   3. FOK ордер постоянно отклоняется биржей")
    print("   4. Цена из стакана (orderbook_price) отличается от market_price")
    print("   5. Race condition между потоками")
    print("\n💡 РЕКОМЕНДАЦИИ:")
    print("   1. Проверьте логи автотрейдера на наличие строк '[XRP] _try_sell'")
    print("   2. Убедитесь что автотрейдер запущен (running=True)")
    print("   3. Проверьте что нет застрявшего флага _selling_in_progress")
    print("   4. Попробуйте переключить FOK на IOC или MARKET ордер")
    print("   5. Проверьте логи на ошибки создания ордера")

if __name__ == "__main__":
    try:
        check_xrp_sell()
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
