#!/usr/bin/env python3
"""Проверка состояния цикла XRP и поиск проблемы с незавершённым циклом"""
import json
from datetime import datetime

# Загружаем состояние
with open('autotrader_cycles_state.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

xrp = data.get('XRP', {})

print("=" * 70)
print("  XRP CYCLE STATE")
print("=" * 70)
print(f"Status: {xrp.get('status')}")
print(f"State: {xrp.get('state')}")
print(f"Start Price: {xrp.get('start_price')}")
print(f"Total Invested: {xrp.get('total_invested_usd')} USDT")
print(f"Base Volume: {xrp.get('base_volume')} XRP")
print(f"Active Step: {xrp.get('active_step')}")
print(f"Total Cycles: {xrp.get('total_cycles_count')}")
print(f"Cycle ID: {xrp.get('cycle_id')}")
print()

# Флаги состояния
print("=" * 70)
print("  ФЛАГИ СОСТОЯНИЯ")
print("=" * 70)
print(f"_buying_in_progress: {xrp.get('_buying_in_progress', 'N/A')}")
print(f"_selling_in_progress: {xrp.get('_selling_in_progress', 'N/A')}")
print(f"manual_pause: {xrp.get('manual_pause', 'N/A')}")
print()

# Последние операции
last_buy_at = xrp.get('last_buy_at')
last_sell_at = xrp.get('last_sell_at')
last_action_at = xrp.get('last_action_at')
cycle_started_at = xrp.get('cycle_started_at')

print("=" * 70)
print("  ВРЕМЕННЫЕ МЕТКИ")
print("=" * 70)
if last_buy_at:
    dt = datetime.fromtimestamp(last_buy_at)
    print(f"Last Buy At: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
    
if last_sell_at:
    dt = datetime.fromtimestamp(last_sell_at)
    print(f"Last Sell At: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
    
if last_action_at:
    dt = datetime.fromtimestamp(last_action_at)
    print(f"Last Action At: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
    
if cycle_started_at:
    dt = datetime.fromtimestamp(cycle_started_at)
    print(f"Cycle Started At: {dt.strftime('%Y-%m-%d %H:%M:%S')}")

print()

# Таблица безубыточности
table = xrp.get('table', [])
print("=" * 70)
print("  ТАБЛИЦА БЕЗУБЫТОЧНОСТИ")
print("=" * 70)
print(f"Table Length: {len(table)} steps")
print()

if table and len(table) > 0:
    step0 = table[0]
    print("STEP 0 (текущий шаг для продажи):")
    print("-" * 70)
    for key, value in step0.items():
        print(f"  {key:25s}: {value}")
    
    print()
    print("=" * 70)
    print("  КРИТИЧЕСКАЯ ДИАГНОСТИКА")
    print("=" * 70)
    
    start_price = xrp.get('start_price', 0)
    rate = step0.get('rate', 0)
    breakeven_price = step0.get('breakeven_price', 0)
    target_delta_pct = step0.get('target_delta_pct', 0)
    
    print(f"Start Price (цена покупки): {start_price:.8f}")
    print(f"Rate (расчётный курс): {rate:.8f}")
    print(f"Breakeven Price: {breakeven_price:.8f}")
    print(f"Target Delta %: {target_delta_pct:.4f}%")
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
        print(f"✅ Target Sell Price выше Start Price на {delta:.4f}%")
        
    if target_delta_pct <= 0:
        print("❌ ОШИБКА: target_delta_pct <= 0!")
        print("   Целевая дельта должна быть положительной!")
    else:
        print(f"✅ Target Delta положительная: {target_delta_pct:.4f}%")
    
    print()
    print("=" * 70)
    print("  АНАЛИЗ ПРОБЛЕМЫ")
    print("=" * 70)
    print("📊 ДАННЫЕ:")
    print(f"   Баланс XRP в кошельке: ~0.00026200 (почти 0)")
    print(f"   Объём в состоянии: {xrp.get('base_volume', 0)} XRP")
    print(f"   Статус цикла: {xrp.get('state', xrp.get('status'))}")
    print()
    print("🔍 ВЫВОД:")
    if xrp.get('base_volume', 0) > 1 and xrp.get('state') == 'active':
        print("   ❌ ПРОБЛЕМА ОБНАРУЖЕНА!")
        print("   • В состоянии указан активный цикл с объёмом")
        print("   • Но баланс XRP почти нулевой")
        print("   • Это означает, что продажа произошла,")
        print("     но цикл НЕ был завершён автотрейдером!")
        print()
        print("🔧 РЕШЕНИЕ:")
        print("   1. Проверить открытые ордера на бирже")
        print("   2. Проверить логи автотрейдера на момент продажи")
        print("   3. Возможно, нужно вручную сбросить цикл")
    elif xrp.get('state') == 'idle':
        print("   ✅ Цикл в состоянии IDLE (ожидание новой покупки)")
    else:
        print(f"   ⚠️ Неопределённое состояние: {xrp.get('state')}")
    
    print()
    print("=" * 70)
    print("  ТЕКУЩАЯ СИТУАЦИЯ")
    print("=" * 70)
    print("Для новой продажи XRP текущая цена должна быть:")
    print(f"  >= {target_sell_price:.8f}")
    print(f"  (т.е. рост >= {target_delta_pct:.4f}% от цены покупки {start_price:.8f})")
    print()
    print("Текущая рыночная цена XRP по данным интерфейса:")
    print(f"  ~2.06 USDT")
    print()
    if 2.06 >= target_sell_price:
        print(f"✅ Текущая цена (2.06) >= целевой ({target_sell_price:.8f})")
        print("   ПРОДАЖА ДОЛЖНА ПРОИСХОДИТЬ!")
    else:
        print(f"❌ Текущая цена (2.06) < целевой ({target_sell_price:.8f})")
        print("   Ожидание роста цены...")
    
print("=" * 70)
