#!/usr/bin/env python3
"""Проверка текущей цены XRP и состояния цикла"""
import json
from datetime import datetime
from gate_api_client import GateAPIClient

# Загружаем API ключ
with open('accounts.json', 'r', encoding='utf-8') as f:
    account = json.load(f)['accounts'][0]

client = GateAPIClient(account['api_key'], account['api_secret'])

# Получаем текущую цену XRP
ticker = client.get_ticker('XRP_USDT')
current_price = float(ticker.get('last', 0))

print("=" * 70)
print("  XRP ТЕКУЩАЯ ЦЕНА")
print("=" * 70)
print(f"Текущая цена XRP: {current_price:.8f} USDT")
print()

# Загружаем состояние цикла
with open('autotrader_cycles_state.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

xrp = data.get('XRP', {})

if not xrp:
    print("⚠️ Цикл XRP не найден в состоянии")
    exit(0)

print("=" * 70)
print("  XRP CYCLE STATE")
print("=" * 70)
print(f"Status: {xrp.get('status')}")
print(f"Start Price: {xrp.get('start_price')}")
print(f"Total Invested: {xrp.get('total_invested_usd')} USDT")
print(f"Base Volume: {xrp.get('base_volume')}")
print(f"Active Step: {xrp.get('active_step')}")
print(f"Total Cycles: {xrp.get('total_cycles_count')}")
print()

# Таблица безубыточности
table = xrp.get('table', [])
if table and len(table) > 0:
    step0 = table[0]
    print("=" * 70)
    print("  STEP 0 (текущий шаг для продажи)")
    print("=" * 70)
    
    start_price = xrp.get('start_price', 0)
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
    
    print("=" * 70)
    print("  КРИТИЧЕСКАЯ ПРОВЕРКА")
    print("=" * 70)
    print(f"Текущая цена XRP:     {current_price:.8f}")
    print(f"Целевая цена продажи: {target_sell_price:.8f}")
    print(f"Цена покупки:         {start_price:.8f}")
    print()
    
    # Проверка условия продажи
    if current_price >= target_sell_price:
        delta_current = ((current_price - start_price) / start_price) * 100
        print(f"✅ УСЛОВИЕ ПРОДАЖИ ВЫПОЛНЕНО!")
        print(f"   {current_price:.8f} >= {target_sell_price:.8f}")
        print(f"   Текущий рост: {delta_current:.2f}%")
        print(f"   Требуемый рост: {target_delta_pct:.2f}%")
        print()
        print("❓ ПОЧЕМУ НЕ ПРОДАЁТ? Возможные причины:")
        print("   1. Флаг _selling_in_progress = True (продажа уже в процессе)")
        print("   2. Есть открытые SELL-ордера на бирже")
        print("   3. Недостаточно монет на балансе")
        print("   4. Автотрейдер не запущен или завис")
    else:
        need_growth = ((target_sell_price - current_price) / current_price) * 100
        print(f"❌ УСЛОВИЕ ПРОДАЖИ НЕ ВЫПОЛНЕНО")
        print(f"   {current_price:.8f} < {target_sell_price:.8f}")
        print(f"   Текущий рост: {((current_price - start_price) / start_price) * 100:.2f}%")
        print(f"   Требуемый рост: {target_delta_pct:.2f}%")
        print(f"   Нужен ещё рост: {need_growth:.2f}%")
    
    print("=" * 70)
