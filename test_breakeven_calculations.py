"""
Тестовая проверка расчётов таблицы безубыточности
"""
from breakeven_calculator import calculate_breakeven_table

# Параметры для теста
params = {
    'steps': 5,
    'start_volume': 10.0,  # $10
    'start_price': 100.0,   # $100 за монету
    'target_r': 3.0,        # R = 3%
    'rk': 0.1,              # Rk = 0.1%
    'pprof': 0.6,           # 0.6%
    'kprof': 0.02,          # 0.02
    'geom_multiplier': 2.0,
    'rebuy_mode': 'geometric',
    'current_price': 100.0
}

print("=" * 80)
print("ТЕСТИРОВАНИЕ РАСЧЁТОВ ТАБЛИЦЫ БЕЗУБЫТОЧНОСТИ")
print("=" * 80)
print(f"\nПараметры:")
print(f"  Стартовая цена (P0): ${params['start_volume']:.2f}")
print(f"  Курс: ${params['start_price']:.2f}")
print(f"  R (базовый шаг): {params['target_r']:.3f}%")
print(f"  Rk (коэффициент): {params['rk']:.3f}%")
print(f"  Геометрия: x{params['geom_multiplier']}")
print(f"  Режим: {params['rebuy_mode']}")
print("\n" + "=" * 80)

table = calculate_breakeven_table(params, current_price=params['current_price'])

print(f"\n{'#':>2} | {'↓,%':>8} | {'↓Δ,%':>8} | {'Курс':>10} | {'Покупка,$':>10} | {'Инв.Сумм':>10} | {'БезУб,$':>10} | {'↑БезУб,%':>10} | {'Монет':>12}")
print("-" * 120)

for row in table:
    step = row['step']
    cum_dec = row['cumulative_decrease_pct']
    step_dec = row['decrease_step_pct']
    rate = row['rate']
    purchase = row['purchase_usd']
    total_inv = row['total_invested']
    be_price = row['breakeven_price']
    be_pct = row['breakeven_pct']
    
    # Рассчитаем количество монет для проверки
    coins = 0
    cum_test = 0.0
    for s in range(step + 1):
        if s == 0:
            p = params['start_volume']
        else:
            p = params['start_volume'] * (params['geom_multiplier'] ** s)
        
        dec_s = -((s * params['rk']) + params['target_r']) if s > 0 else 0.0
        if s > 0:
            cum_test += dec_s
        
        r_s = params['start_price'] * (1 + cum_test / 100.0)
        coins += p / r_s
    
    print(f"{step:>2} | {cum_dec:>8.3f} | {step_dec:>8.3f} | {rate:>10.4f} | {purchase:>10.2f} | {total_inv:>10.2f} | {be_price:>10.4f} | {be_pct:>10.2f} | {coins:>12.6f}")

print("\n" + "=" * 120)
print("\nПРОВЕРКА ФОРМУЛ:")
print("-" * 80)

# Проверим шаг 3
step_3 = table[3]
print(f"\nШаг 3:")
print(f"  1. Шаг снижения: -((3 × {params['rk']}) + {params['target_r']}) = {step_3['decrease_step_pct']:.3f}%")
print(f"  2. Накопленное снижение: {step_3['cumulative_decrease_pct']:.3f}%")
print(f"  3. Курс: {params['start_price']} × (1 + {step_3['cumulative_decrease_pct']:.3f}/100) = {step_3['rate']:.4f}")
print(f"  4. Сумма покупки: {params['start_volume']} × {params['geom_multiplier']}³ = {step_3['purchase_usd']:.2f}")
print(f"  5. Всего инвестировано: {step_3['total_invested']:.2f}")
print(f"  6. Цена безубыточности: {step_3['breakeven_price']:.4f}")
print(f"  7. Рост для безубытка: {step_3['breakeven_pct']:.2f}%")

# Ручная проверка цены безубыточности для шага 3
print(f"\n  РУЧНАЯ ПРОВЕРКА цены безубыточности:")
cum_manual = 0.0
total_coins_manual = 0.0
total_inv_manual = 0.0

for s in range(4):  # 0, 1, 2, 3
    if s == 0:
        purchase = params['start_volume']
    else:
        purchase = params['start_volume'] * (params['geom_multiplier'] ** s)
    
    dec = -((s * params['rk']) + params['target_r']) if s > 0 else 0.0
    if s > 0:
        cum_manual += dec
    
    rate_s = params['start_price'] * (1 + cum_manual / 100.0)
    coins_s = purchase / rate_s
    
    total_inv_manual += purchase
    total_coins_manual += coins_s
    
    print(f"    Шаг {s}: покупка=${purchase:.2f}, курс=${rate_s:.4f}, монет={coins_s:.6f}, накопл.%={cum_manual:.3f}%")

be_manual = total_inv_manual / total_coins_manual
print(f"\n  Всего инвестировано: ${total_inv_manual:.2f}")
print(f"  Всего монет: {total_coins_manual:.6f}")
print(f"  Цена безубыточности (ручной расчёт): ${be_manual:.4f}")
print(f"  Цена безубыточности (из функции): ${step_3['breakeven_price']:.4f}")
print(f"  Разница: {abs(be_manual - step_3['breakeven_price']):.6f}")

print("\n" + "=" * 120)
print("ПРОВЕРКА ЗАВЕРШЕНА")
print("=" * 120)
