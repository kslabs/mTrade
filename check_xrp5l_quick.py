"""
Быстрая проверка: почему XRP5L не продаёт
"""
import sys
sys.path.append('.')

from autotrader_v2 import AutoTraderV2
from state_manager import StateManager

base = "XRP5L"
quote = "USDT"

# Текущие данные
current_price = 0.04697
start_price = 0.0467

print(f"\n{'='*60}")
print(f"БЫСТРАЯ ПРОВЕРКА: {base}")
print(f"{'='*60}\n")

# Инициализируем state_manager
state_manager = StateManager()

# Получаем параметры из файла
params = state_manager.get_breakeven_params(base)
if params:
    print(f"📋 Параметры найдены:")
    print(f"   profit (pprof): {params.get('pprof', 'НЕТ')}%")
    print(f"   steps: {params.get('steps', 'НЕТ')}")
    print(f"   geom_multiplier: {params.get('geom_multiplier', 'НЕТ')}")
    print(f"   orderbook_level: {params.get('orderbook_level', 'НЕТ')}")

# Проверяем состояние цикла
cycle_data = state_manager.load_cycle_state(base)
if cycle_data:
    print(f"\n📊 Состояние цикла:")
    print(f"   active: {cycle_data.get('active', False)}")
    print(f"   active_step: {cycle_data.get('active_step', -1)}")
    print(f"   start_price: {cycle_data.get('start_price', 'НЕТ')}")
    print(f"   last_buy_price: {cycle_data.get('last_buy_price', 'НЕТ')}")
    print(f"   total_invested_usd: {cycle_data.get('total_invested_usd', 'НЕТ')}")
    print(f"   base_volume: {cycle_data.get('base_volume', 'НЕТ')}")
    
    # Проверяем таблицу
    table = cycle_data.get('table', [])
    if table and len(table) > 0:
        print(f"\n📈 Таблица безубыточности (шаг 0):")
        row = table[0]
        rate = row.get('rate', 0)
        be_price = row.get('breakeven_price', 0)
        target_delta = row.get('target_delta_pct', 0)
        
        print(f"   rate (last buy): {rate:.8f}")
        print(f"   breakeven_price: {be_price:.8f}")
        print(f"   target_delta_pct: {target_delta:.4f}%")
        
        required_price = rate * (1 + target_delta / 100.0)
        print(f"\n🎯 УСЛОВИЕ ПРОДАЖИ:")
        print(f"   Required price: {required_price:.8f}")
        print(f"   Current price: {current_price:.8f}")
        print(f"   Условие: {current_price:.8f} >= {required_price:.8f} ?")
        
        if current_price >= required_price:
            print(f"   ✅ УСЛОВИЕ ВЫПОЛНЕНО!")
            print(f"\n⚠️ Если продажа не происходит, возможные причины:")
            print(f"      1. Цена из стакана ниже required_price")
            print(f"      2. Продажа уже в процессе (_selling_in_progress=True)")
            print(f"      3. Есть открытые SELL ордера")
            print(f"      4. Недостаточно баланса {base}")
        else:
            diff = required_price - current_price
            diff_pct = (diff / required_price) * 100
            print(f"   ❌ УСЛОВИЕ НЕ ВЫПОЛНЕНО")
            print(f"   Не хватает: {diff:.8f} ({diff_pct:.2f}%)")
            print(f"\n💡 Цена должна вырасти ещё на {diff_pct:.2f}% для продажи")
    else:
        print(f"\n❌ Таблица безубыточности пустая!")
else:
    print(f"\n❌ Цикл не найден!")

print(f"\n{'='*60}\n")
