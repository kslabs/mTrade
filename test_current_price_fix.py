"""
Тест исправления: проверка, что current_price всегда используется при пересчёте таблицы
"""

from breakeven_calculator import calculate_breakeven_table

# Параметры с НЕ нулевой start_price
params = {
    'steps': 16,
    'start_volume': 3.0,
    'start_price': 2.116,  # Старое значение
    'pprof': 0.6,
    'kprof': 0.02,
    'target_r': 3.65,
    'rk': 0.0,
    'geom_multiplier': 2.0,
    'rebuy_mode': 'geometric'
}

print("=== ТЕСТ ИСПРАВЛЕНИЯ ===")
print(f"params['start_price'] = {params['start_price']}")
print(f"")

# Пересчитываем таблицу с НОВОЙ ценой покупки
executed_price = 2.117  # Реальная цена покупки
print(f"Пересчитываем таблицу с executed_price = {executed_price}")

table = calculate_breakeven_table(params, current_price=executed_price)

step0 = table[0]
print(f"")
print(f"Результат (шаг 0):")
print(f"  rate (расчётный курс): {step0['rate']}")
print(f"  breakeven_price: {step0['breakeven_price']}")
print(f"  target_delta_pct: {step0['target_delta_pct']}%")
print(f"")

# Проверка
if step0['rate'] == executed_price:
    print("✅ ПРАВИЛЬНО: Таблица рассчитана с executed_price!")
    print(f"   rate == executed_price ({step0['rate']} == {executed_price})")
else:
    print("❌ ОШИБКА: Таблица НЕ рассчитана с executed_price!")
    print(f"   rate != executed_price ({step0['rate']} != {executed_price})")
    print(f"   Используется старое значение из params['start_price']")

print(f"")
print("=== ТЕСТ С current_price = 0 ===")

# Если current_price не передан, должен использоваться params['start_price']
table2 = calculate_breakeven_table(params, current_price=0)
step0_2 = table2[0]

print(f"params['start_price'] = {params['start_price']}")
print(f"current_price = 0")
print(f"Результат: rate = {step0_2['rate']}")

if step0_2['rate'] == params['start_price']:
    print("✅ ПРАВИЛЬНО: Используется params['start_price']")
else:
    print("❌ ОШИБКА: Должно использоваться params['start_price']")
