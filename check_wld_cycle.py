#!/usr/bin/env python3
"""Проверка состояния цикла WLD и анализ последней продажи"""
import json
from datetime import datetime

# Загружаем состояние
with open('autotrader_cycles_state.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

wld = data.get('WLD', {})

print("=" * 70)
print("  WLD CYCLE STATE")
print("=" * 70)
print(f"Status: {wld.get('status')}")
print(f"Start Price: {wld.get('start_price')}")
print(f"Total Invested: {wld.get('total_invested_usd')} USDT")
print(f"Base Volume: {wld.get('base_volume')}")
print(f"Active Step: {wld.get('active_step')}")
print(f"Total Cycles: {wld.get('total_cycles_count')}")
print()

# Последние операции
last_buy_at = wld.get('last_buy_at')
last_sell_at = wld.get('last_sell_at')

if last_buy_at:
    dt = datetime.fromtimestamp(last_buy_at)
    print(f"Last Buy At: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
    
if last_sell_at:
    dt = datetime.fromtimestamp(last_sell_at)
    print(f"Last Sell At: {dt.strftime('%Y-%m-%d %H:%M:%S')}")

print()

# Таблица безубыточности
table = wld.get('table', [])
print(f"Table Length: {len(table)} steps")
print()

if table and len(table) > 0:
    step0 = table[0]
    print("=" * 70)
    print("  STEP 0 (текущий шаг для продажи)")
    print("=" * 70)
    for key, value in step0.items():
        print(f"{key:25s}: {value}")
    
    print()
    print("=" * 70)
    print("  КРИТИЧЕСКАЯ ПРОВЕРКА")
    print("=" * 70)
    
    start_price = wld.get('start_price', 0)
    rate = step0.get('rate', 0)
    breakeven_price = step0.get('breakeven_price', 0)
    target_delta_pct = step0.get('target_delta_pct', 0)
    
    print(f"Start Price (цена покупки): {start_price:.8f}")
    print(f"Rate (расчётный курс): {rate:.8f}")
    print(f"Breakeven Price: {breakeven_price:.8f}")
    print(f"Target Delta %: {target_delta_pct:.2f}%")
    print()
    
    # Вычисляем целевую цену продажи
    target_sell_price = start_price * (1 + target_delta_pct / 100.0)
    print(f"Target Sell Price (вычислено): {target_sell_price:.8f}")
    print()
    
    # Проверка
    if target_sell_price <= start_price:
        print("❌ ОШИБКА: target_sell_price <= start_price!")
        print("   Продажа будет по цене покупки или ниже!")
    else:
        delta = ((target_sell_price - start_price) / start_price) * 100
        print(f"✅ Target Sell Price выше Start Price на {delta:.2f}%")
        
    if target_delta_pct <= 0:
        print("❌ ОШИБКА: target_delta_pct <= 0!")
        print("   Целевая дельта должна быть положительной!")
    else:
        print(f"✅ Target Delta положительная: {target_delta_pct:.2f}%")
    
    print()
    print("=" * 70)
    print("  ТЕКУЩАЯ СИТУАЦИЯ")
    print("=" * 70)
    print("Чтобы продать WLD с профитом, текущая цена должна быть:")
    print(f"  >= {target_sell_price:.8f}")
    print(f"  (т.е. рост >= {target_delta_pct:.2f}% от цены покупки {start_price:.8f})")
    print("=" * 70)
