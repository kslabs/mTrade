"""
Проверка условий продажи для XRP5L
"""
import sys
sys.path.append('.')

from state_manager import StateManager
from breakeven_calculator import calculate_breakeven_table

# Данные из интерфейса
base = "XRP5L"
quote = "USDT"
current_price = 0.04697
orderbook_price = 0.04697  # Предполагаем, что стакан показывает ту же цену
start_price = 0.0467
be_price = 0.0467
last_buy_price = 0.0467

print(f"\n{'='*60}")
print(f"ДИАГНОСТИКА ПРОДАЖИ: {base}")
print(f"{'='*60}\n")

# Инициализируем state_manager
state_manager = StateManager()

# Получаем параметры
params = state_manager.get_breakeven_params(base)
if not params:
    print(f"❌ Параметры не найдены для {base}")
    sys.exit(1)

print(f"📋 ПАРАМЕТРЫ:")
print(f"   Все параметры: {params}")
print(f"   start_amount_usd: {params.get('start_amount_usd', params.get('start_amount_usdt', 'НЕТ'))}")
print(f"   profit_pct: {params.get('profit_pct', params.get('profit_percent', 'НЕТ'))}")
print(f"   max_steps: {params.get('max_steps', 'НЕТ')}")
print(f"   geom_multiplier: {params.get('geom_multiplier', 'НЕТ')}")
print(f"   orderbook_level: {params.get('orderbook_level', 'НЕТ')}")

# Генерируем таблицу
table = calculate_breakeven_table(
    start_price=start_price,
    start_amount_usd=params.get('start_amount_usd', 18.0),
    profit_pct=params.get('profit_pct', 0.5),
    max_steps=params.get('max_steps', 16),
    geom_multiplier=params.get('geom_multiplier', 1.3),
    step_down_pct=params.get('step_down_pct', 1.0),
    orderbook_level=params.get('orderbook_level', 1)
)

print(f"\n📊 ТАБЛИЦА БЕЗУБЫТОЧНОСТИ (первые 3 строки):")
for i in range(min(3, len(table))):
    row = table[i]
    print(f"\nШаг {i}:")
    print(f"   rate: {row['rate']:.8f}")
    print(f"   breakeven_price: {row['breakeven_price']:.8f}")
    print(f"   target_delta_pct: {row['target_delta_pct']:.4f}%")

# Проверяем условие продажи для шага 0
active_step = 0
row = table[active_step]
rate = row['rate']
breakeven_price = row['breakeven_price']
target_delta_pct = row['target_delta_pct']

required_price = rate * (1 + target_delta_pct / 100.0)
current_growth_from_rate = ((current_price - rate) / rate) * 100.0

print(f"\n{'='*60}")
print(f"🔍 ПРОВЕРКА УСЛОВИЯ ПРОДАЖИ (ШАГ {active_step})")
print(f"{'='*60}\n")

print(f"📈 ЦЕНЫ:")
print(f"   Start price (P0): {start_price:.8f}")
print(f"   Last buy rate: {rate:.8f}")
print(f"   Breakeven price (BE): {breakeven_price:.8f}")
print(f"   Current price: {current_price:.8f}")
print(f"   Orderbook price: {orderbook_price:.8f}")

print(f"\n📊 УСЛОВИЕ:")
print(f"   Target Δ % (от rate): {target_delta_pct:.4f}%")
print(f"   Required price: {required_price:.8f}")
print(f"   Current growth from rate: {current_growth_from_rate:.4f}%")

print(f"\n✅ ПРОВЕРКА #1: Ticker price >= Required price?")
print(f"   {current_price:.8f} >= {required_price:.8f} ?")
if current_price >= required_price:
    print(f"   ✅ ДА, условие выполнено")
else:
    print(f"   ❌ НЕТ, условие НЕ выполнено")
    print(f"   Недостаточно: {(required_price - current_price):.8f} ({((required_price - current_price) / required_price * 100):.2f}%)")

print(f"\n✅ ПРОВЕРКА #2: Orderbook price >= Required price?")
print(f"   {orderbook_price:.8f} >= {required_price:.8f} ?")
if orderbook_price >= required_price:
    print(f"   ✅ ДА, условие выполнено")
else:
    print(f"   ❌ НЕТ, условие НЕ выполнено")
    print(f"   Недостаточно: {(required_price - orderbook_price):.8f} ({((required_price - orderbook_price) / required_price * 100):.2f}%)")

print(f"\n{'='*60}")
print(f"ВЫВОД:")
print(f"{'='*60}")

if current_price >= required_price and orderbook_price >= required_price:
    print(f"✅ ОБА УСЛОВИЯ ВЫПОЛНЕНЫ - ПРОДАЖА ДОЛЖНА ПРОИЗОЙТИ!")
elif current_price >= required_price:
    print(f"⚠️ Ticker выше, но ORDERBOOK НИЖЕ требуемой цены")
    print(f"   Это нормально - защита от продажи по низкой цене в стакане")
else:
    print(f"❌ TICKER ЦЕНА НИЖЕ ТРЕБУЕМОЙ - продажа не произойдёт")

print(f"\n{'='*60}\n")
