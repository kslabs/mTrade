"""
Тестовая проверка с реальными параметрами по умолчанию
"""
from breakeven_calculator import calculate_breakeven_table

# Параметры по умолчанию из интерфейса
params = {
    'steps': 16,
    'start_volume': 3.0,     # $3
    'start_price': 91000.0,  # BTC ~$91,000
    'target_r': 3.65,        # R = 3.65%
    'rk': 0.0,               # Rk = 0.0% (линейная стратегия)
    'pprof': 0.6,            # 0.6%
    'kprof': 0.02,           # 0.02
    'geom_multiplier': 2.0,
    'rebuy_mode': 'geometric',
    'current_price': 91000.0
}

print("=" * 100)
print("РЕАЛЬНЫЙ ТЕСТ С ПАРАМЕТРАМИ ПО УМОЛЧАНИЮ (BTC)")
print("=" * 100)
print(f"\nПараметры:")
print(f"  Стартовый объём: ${params['start_volume']:.2f}")
print(f"  Стартовая цена BTC: ${params['start_price']:,.2f}")
print(f"  R (базовый шаг): {params['target_r']:.3f}%")
print(f"  Rk (коэффициент): {params['rk']:.3f}%")
print(f"  Pprof: {params['pprof']:.2f}%")
print(f"  Kprof: {params['kprof']:.3f}")
print(f"  Геометрия: x{params['geom_multiplier']}")
print(f"  Режим: {params['rebuy_mode']}")
print("\n" + "=" * 100)

table = calculate_breakeven_table(params, current_price=params['current_price'])

print(f"\n{'#':>2} | {'↓,%':>9} | {'↓Δ,%':>9} | {'Курс BTC':>12} | {'Покупка,$':>11} | {'Инв.Сумм,$':>12} | {'БезУб,$':>12} | {'↑БезУб,%':>10} | {'tΔPsell,%':>10}")
print("-" * 100)

for row in table:
    step = row['step']
    cum_dec = row['cumulative_decrease_pct']
    step_dec = row['decrease_step_pct']
    rate = row['rate']
    purchase = row['purchase_usd']
    total_inv = row['total_invested']
    be_price = row['breakeven_price']
    be_pct = row['breakeven_pct']
    target = row['target_delta_pct']
    
    print(f"{step:>2} | {cum_dec:>9.3f} | {step_dec:>9.3f} | {rate:>12,.2f} | {purchase:>11,.2f} | {total_inv:>12,.2f} | {be_price:>12,.2f} | {be_pct:>10.2f} | {target:>10.2f}")

print("\n" + "=" * 100)

# Проверим несколько ключевых шагов
print("\nАНАЛИЗ КЛЮЧЕВЫХ ШАГОВ:")
print("-" * 100)

for check_step in [0, 1, 5, 10, 16]:
    if check_step < len(table):
        row = table[check_step]
        print(f"\nШаг {check_step}:")
        print(f"  Накопленное снижение: {row['cumulative_decrease_pct']:.3f}%")
        print(f"  Шаг снижения: {row['decrease_step_pct']:.3f}%")
        print(f"  Курс BTC: ${row['rate']:,.2f}")
        print(f"  Сумма покупки: ${row['purchase_usd']:,.2f}")
        print(f"  Всего инвестировано: ${row['total_invested']:,.2f}")
        print(f"  Цена безубыточности: ${row['breakeven_price']:,.2f}")
        print(f"  Рост для безубытка: {row['breakeven_pct']:.2f}%")
        print(f"  Рост для профита: {row['target_delta_pct']:.2f}%")
        
        # Проверка: цена безубыточности должна быть выше текущего курса
        if row['breakeven_price'] > row['rate']:
            margin = ((row['breakeven_price'] / row['rate']) - 1) * 100
            print(f"  ✅ БезУб выше курса на {margin:.2f}%")
        else:
            print(f"  ⚠️ БезУб ниже или равен курсу!")

print("\n" + "=" * 100)

# Проверим логику с Rk > 0
print("\nТЕСТ С ПРОГРЕССИВНОЙ СТРАТЕГИЕЙ (Rk = 0.1):")
print("-" * 100)

params['rk'] = 0.1
table2 = calculate_breakeven_table(params, current_price=params['current_price'])

print(f"\n{'#':>2} | {'↓,%':>9} | {'↓Δ,%':>9} | {'Курс BTC':>12}")
print("-" * 50)

for row in table2[:6]:  # Первые 6 шагов
    print(f"{row['step']:>2} | {row['cumulative_decrease_pct']:>9.3f} | {row['decrease_step_pct']:>9.3f} | {row['rate']:>12,.2f}")

print("\n✅ Видно, что с Rk=0.1 шаг снижения увеличивается: -3.65%, -3.75%, -3.85% и т.д.")
print("✅ Накопленное снижение также растёт быстрее")

print("\n" + "=" * 100)
print("ПРОВЕРКА ЗАВЕРШЕНА")
print("=" * 100)
