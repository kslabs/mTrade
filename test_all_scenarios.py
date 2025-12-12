"""
Полный тест всех сценариев использования calculate_breakeven_table
"""

from breakeven_calculator import calculate_breakeven_table

params = {
    'steps': 16,
    'start_volume': 3.0,
    'start_price': 2.5,  # Есть значение в параметрах
    'pprof': 0.6,
    'kprof': 0.02,
    'target_r': 3.65,
    'rk': 0.0,
    'geom_multiplier': 2.0,
    'rebuy_mode': 'geometric'
}

print("=== ТЕСТ ВСЕХ СЦЕНАРИЕВ ===\n")

# Сценарий 1: current_price > 0 (пересчёт после покупки)
print("1. Пересчёт с новой ценой (current_price=2.117, params['start_price']=2.5)")
table1 = calculate_breakeven_table(params, current_price=2.117)
print(f"   Результат: rate = {table1[0]['rate']}")
print(f"   Ожидается: rate = 2.117")
if table1[0]['rate'] == 2.117:
    print("   ✅ ПРАВИЛЬНО: используется current_price\n")
else:
    print("   ❌ ОШИБКА\n")

# Сценарий 2: current_price = 0, params['start_price'] > 0
print("2. Расчёт с существующей start_price (current_price=0, params['start_price']=2.5)")
table2 = calculate_breakeven_table(params, current_price=0)
print(f"   Результат: rate = {table2[0]['rate']}")
print(f"   Ожидается: rate = 2.5")
if table2[0]['rate'] == 2.5:
    print("   ✅ ПРАВИЛЬНО: используется params['start_price']\n")
else:
    print("   ❌ ОШИБКА\n")

# Сценарий 3: current_price = 0, params['start_price'] = 0
params_no_start = params.copy()
params_no_start['start_price'] = 0
print("3. Расчёт без start_price (current_price=0, params['start_price']=0)")
table3 = calculate_breakeven_table(params_no_start, current_price=0)
print(f"   Результат: rate = {table3[0]['rate']}")
print(f"   Ожидается: rate = 1.0 (значение по умолчанию)")
if table3[0]['rate'] == 1.0:
    print("   ✅ ПРАВИЛЬНО: используется значение по умолчанию\n")
else:
    print("   ❌ ОШИБКА\n")

# Сценарий 4: current_price > 0, params['start_price'] = 0
print("4. Расчёт с current_price, без start_price (current_price=2.3, params['start_price']=0)")
table4 = calculate_breakeven_table(params_no_start, current_price=2.3)
print(f"   Результат: rate = {table4[0]['rate']}")
print(f"   Ожидается: rate = 2.3")
if table4[0]['rate'] == 2.3:
    print("   ✅ ПРАВИЛЬНО: используется current_price\n")
else:
    print("   ❌ ОШИБКА\n")

# Сценарий 5: Симуляция реального процесса
print("5. РЕАЛЬНЫЙ ПРОЦЕСС: стартовая покупка + пересчёт")
print("   a) Первый расчёт (перед покупкой, current_price=2.5)")
params_real = params.copy()
params_real['start_price'] = 0  # Ещё не было покупок
table5a = calculate_breakeven_table(params_real, current_price=2.5)
print(f"      rate = {table5a[0]['rate']} (должно быть 2.5)")

print("   b) Покупка исполнена по цене 2.485")
executed_price = 2.485

print("   c) Обновляем start_price в параметрах")
params_real['start_price'] = executed_price

print("   d) Пересчитываем таблицу с реальной ценой покупки")
table5b = calculate_breakeven_table(params_real, current_price=executed_price)
print(f"      rate = {table5b[0]['rate']} (должно быть {executed_price})")

if table5b[0]['rate'] == executed_price:
    print("   ✅ ПРАВИЛЬНО: таблица пересчитана с реальной ценой покупки\n")
else:
    print(f"   ❌ ОШИБКА: rate = {table5b[0]['rate']}, ожидается {executed_price}\n")

print("=== ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ ===")
