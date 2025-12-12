"""
Тест расчёта целевой цены продажи

Проверяет, какие значения получаются из breakeven_calculator
"""

from breakeven_calculator import calculate_breakeven_table

# Параметры для XRP (примерные)
params = {
    'steps': 16,
    'start_volume': 10.0,  # $10
    'start_price': 2.0780,  # Стартовая цена из лога
    'pprof': 0.15,  # Целевая прибыль 0.15%
    'kprof': 0.035,  # Коэффициент уменьшения прибыли
    'target_r': 3.65,  # R - шаг изменения процента закупки
    'rk': 0.0,  # Rk - коэффициент изменения шага
    'geom_multiplier': 2.0,
    'rebuy_mode': 'geometric'
}

print("=" * 80)
print("ТЕСТ РАСЧЁТА ЦЕЛЕВОЙ ЦЕНЫ ПРОДАЖИ")
print("=" * 80)
print()

# Рассчитываем таблицу для текущей цены
current_price = 2.0780
table = calculate_breakeven_table(params, current_price=current_price)

print(f"Стартовая цена: {current_price}")
print(f"Параметры:")
print(f"  - pprof (целевая прибыль): {params['pprof']}%")
print(f"  - kprof (коэффициент): {params['kprof']}%")
print()

# Проверяем шаг 0 (стартовая покупка)
step_0 = table[0]
print("Шаг 0 (стартовая покупка):")
print(f"  rate (расчётный курс): {step_0['rate']}")
print(f"  breakeven_price (цена безубыточности): {step_0['breakeven_price']}")
print(f"  target_delta_pct (целевая дельта): {step_0['target_delta_pct']}%")
print()

# Вычисляем целевую цену продажи СТАРЫМ способом (неправильно)
target_sell_price_OLD = step_0['breakeven_price'] * (1 + step_0['target_delta_pct'] / 100.0)
print(f"❌ СТАРЫЙ расчёт (неправильно):")
print(f"  target_sell_price = {step_0['breakeven_price']} * (1 + {step_0['target_delta_pct']}/100)")
print(f"  target_sell_price = {target_sell_price_OLD:.8f}")
print()

# Вычисляем целевую цену продажи НОВЫМ способом (правильно)
target_sell_price_NEW = step_0['rate'] * (1 + step_0['target_delta_pct'] / 100.0)
print(f"✅ НОВЫЙ расчёт (правильно):")
print(f"  target_sell_price = {step_0['rate']} * (1 + {step_0['target_delta_pct']}/100)")
print(f"  target_sell_price = {target_sell_price_NEW:.8f}")
print()

# Применяем защиту от убытков
if target_sell_price_NEW < step_0['breakeven_price']:
    print(f"⚠️ Целевая цена ниже безубыточности, применяем защиту:")
    print(f"  target_sell_price = max({target_sell_price_NEW:.8f}, {step_0['breakeven_price']:.8f})")
    target_sell_price_NEW = step_0['breakeven_price']
    print(f"  target_sell_price = {target_sell_price_NEW:.8f}")
    print()

# Проверяем условие продажи для разных цен
print("=" * 80)
print("ПРОВЕРКА УСЛОВИЯ ПРОДАЖИ")
print("=" * 80)
print()

test_prices = [2.0760, 2.0770, 2.0780, 2.0790, 2.0800, 2.0810, 2.0820]
for test_price in test_prices:
    will_sell = test_price >= target_sell_price_NEW
    status = "✅ ПРОДАЁМ" if will_sell else "⛔ НЕ ПРОДАЁМ"
    print(f"Цена: {test_price:.4f} → {status} (порог: {target_sell_price_NEW:.8f})")

print()
print("=" * 80)
