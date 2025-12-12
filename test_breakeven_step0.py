"""
Проверка расчёта целевой цены продажи для шага 0 (стартовая покупка)
"""

from breakeven_calculator import calculate_breakeven_table

# Пример параметров
params = {
    'steps': 16,
    'start_volume': 3.0,
    'start_price': 2.5,  # Будет заменено на executed_price
    'pprof': 0.6,
    'kprof': 0.02,
    'target_r': 3.65,
    'rk': 0.0,
    'geom_multiplier': 2.0,
    'rebuy_mode': 'geometric'
}

# Симуляция покупки
executed_price = 2.5  # Цена, по которой была куплена монета

# Пересчитываем таблицу с реальной ценой покупки
table = calculate_breakeven_table(params, current_price=executed_price)

# Проверяем шаг 0 (стартовая покупка)
step0 = table[0]

print("=== АНАЛИЗ ШАГА 0 (СТАРТОВАЯ ПОКУПКА) ===")
print(f"Цена покупки (executed_price): {executed_price}")
print(f"")
print(f"Данные из таблицы (шаг 0):")
print(f"  rate (расчётный курс): {step0['rate']}")
print(f"  breakeven_price (цена безубыточности): {step0['breakeven_price']}")
print(f"  breakeven_pct (рост до безубытка от rate): {step0['breakeven_pct']:.4f}%")
print(f"  target_delta_pct (целевой рост от rate): {step0['target_delta_pct']:.4f}%")
print(f"")

# Рассчитываем целевую цену продажи (как в коде автотрейдера)
rate = step0['rate']
target_delta_pct = step0['target_delta_pct']
breakeven_price = step0['breakeven_price']

target_sell_price = rate * (1 + target_delta_pct / 100.0)

# Дополнительная защита из кода
if target_sell_price < breakeven_price:
    print(f"⚠️ ВНИМАНИЕ: Целевая цена ({target_sell_price}) ниже безубыточности ({breakeven_price})")
    target_sell_price = breakeven_price

print(f"Расчёт целевой цены продажи:")
print(f"  target_sell_price = rate × (1 + target_delta_pct / 100)")
print(f"  target_sell_price = {rate} × (1 + {target_delta_pct:.4f} / 100)")
print(f"  target_sell_price = {rate} × {1 + target_delta_pct / 100.0}")
print(f"  target_sell_price = {target_sell_price:.8f}")
print(f"")

# Проверяем, что целевая цена выше цены покупки
profit_from_buy = target_sell_price - executed_price
profit_pct_from_buy = (profit_from_buy / executed_price) * 100.0

print(f"Проверка профита:")
print(f"  Разница: {target_sell_price:.8f} - {executed_price:.8f} = {profit_from_buy:.8f}")
print(f"  Процент от покупки: {profit_pct_from_buy:+.4f}%")
print(f"")

if target_sell_price > executed_price:
    print("✅ ПРАВИЛЬНО: Целевая цена продажи ВЫШЕ цены покупки")
    print(f"   Ожидаемый профит: +{profit_pct_from_buy:.2f}%")
else:
    print("❌ ОШИБКА: Целевая цена продажи НЕ ВЫШЕ цены покупки!")
    print(f"   Будет убыток: {profit_pct_from_buy:.2f}%")

print(f"")
print("=== ПРОВЕРКА С ДРУГОЙ ЦЕНОЙ ПОКУПКИ ===")

# Симуляция покупки по другой цене (например, XRP)
executed_price2 = 2.15  # Допустим, купили по 2.15

# Важно: после покупки start_price должен обновиться!
params['start_price'] = executed_price2
table2 = calculate_breakeven_table(params, current_price=executed_price2)

step0_2 = table2[0]
rate2 = step0_2['rate']
target_delta_pct2 = step0_2['target_delta_pct']
breakeven_price2 = step0_2['breakeven_price']

target_sell_price2 = rate2 * (1 + target_delta_pct2 / 100.0)
if target_sell_price2 < breakeven_price2:
    target_sell_price2 = breakeven_price2

profit_from_buy2 = target_sell_price2 - executed_price2
profit_pct_from_buy2 = (profit_from_buy2 / executed_price2) * 100.0

print(f"Цена покупки: {executed_price2}")
print(f"Целевая цена продажи: {target_sell_price2:.8f}")
print(f"Ожидаемый профит: {profit_pct_from_buy2:+.4f}%")

if target_sell_price2 > executed_price2:
    print("✅ ПРАВИЛЬНО")
else:
    print("❌ ОШИБКА")
