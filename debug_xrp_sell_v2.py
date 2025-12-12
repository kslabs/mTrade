"""
Диагностика продажи XRP - почему не продается при выполненном условии
"""

import json
import os

# Загружаем состояние цикла
STATE_FILE = "autotrader_cycles_state.json"

if not os.path.exists(STATE_FILE):
    print("❌ Файл состояния не найден!")
    exit(1)

with open(STATE_FILE, 'r', encoding='utf-8') as f:
    state = json.load(f)

base = 'XRP'

if base not in state:
    print(f"❌ Валюта {base} не найдена в состоянии!")
    exit(1)

cycle = state[base]

print("=" * 80)
print("🔍 ДИАГНОСТИКА ПРОДАЖИ XRP")
print("=" * 80)

print("\n📊 СОСТОЯНИЕ ЦИКЛА:")
print(f"  active: {cycle.get('active')}")
print(f"  active_step: {cycle.get('active_step')}")
print(f"  start_price: {cycle.get('start_price')}")
print(f"  last_buy_price: {cycle.get('last_buy_price')}")
print(f"  base_volume: {cycle.get('base_volume')}")
print(f"  total_invested_usd: {cycle.get('total_invested_usd')}")
print(f"  status: {cycle.get('status')}")

# Проверяем таблицу
table = cycle.get('table', [])
if not table:
    print("\n❌ ТАБЛИЦА ПУСТА!")
    exit(1)

print(f"\n📋 ТАБЛИЦА BREAKEVEN (всего шагов: {len(table)}):")

active_step = cycle.get('active_step', 0)
if active_step < 0 or active_step >= len(table):
    print(f"❌ Некорректный active_step: {active_step}")
    exit(1)

# Выводим текущий шаг
row = table[active_step]
print(f"\n🎯 ТЕКУЩИЙ ШАГ [{active_step}]:")
print(f"  rate: {row.get('rate')}")
print(f"  breakeven_pct: {row.get('breakeven_pct')}%")
print(f"  target_delta_pct: {row.get('target_delta_pct')}%")
print(f"  orderbook_level: {row.get('orderbook_level')}")
print(f"  purchase_usd: {row.get('purchase_usd')}")

# Рассчитываем условие продажи
start_price = cycle.get('start_price', 0)
breakeven_pct = float(row.get('breakeven_pct', 0))
required_price = start_price * (1 + breakeven_pct / 100.0)

print(f"\n💰 УСЛОВИЕ ПРОДАЖИ:")
print(f"  start_price: {start_price:.8f}")
print(f"  breakeven_pct: {breakeven_pct:.4f}%")
print(f"  required_price: {required_price:.8f}")

# Текущая цена (вводим вручную или берем из WebSocket)
current_price = 2.042  # ИЗ ВАШИХ ДАННЫХ

print(f"\n🔍 ПРОВЕРКА:")
print(f"  Текущая цена: {current_price:.8f}")
print(f"  Требуемая цена: {required_price:.8f}")
print(f"  Условие: {current_price:.8f} >= {required_price:.8f} ?")

if current_price >= required_price:
    print(f"  ✅ УСЛОВИЕ ВЫПОЛНЕНО! (рост: {((current_price - start_price) / start_price * 100):.2f}%)")
    print("\n🔴 ПОЧЕМУ НЕ ПРОДАЕТСЯ?")
    print("\nВОЗМОЖНЫЕ ПРИЧИНЫ:")
    print("1. Флаг _selling_in_progress=True (продажа уже в процессе)")
    print("2. Открытые SELL ордера на бирже")
    print("3. base_volume <= 0 (нечего продавать)")
    print("4. FOK ордер постоянно отклоняется биржей")
    print("5. Ошибка при создании ордера (проверьте логи автотрейдера)")
else:
    print(f"  ❌ УСЛОВИЕ НЕ ВЫПОЛНЕНО (не хватает {((required_price - current_price) / start_price * 100):.2f}%)")

# Проверяем флаги (если они сохранены)
if '_selling_in_progress' in cycle:
    print(f"\n⚠️ ФЛАГ _selling_in_progress: {cycle['_selling_in_progress']}")

print("\n" + "=" * 80)
print("📝 РЕКОМЕНДАЦИИ:")
print("=" * 80)
print("1. Проверьте логи автотрейдера (ищите строки с [XRP] _try_sell)")
print("2. Убедитесь, что нет открытых SELL ордеров на бирже")
print("3. Проверьте, что base_volume > 0")
print("4. Если FOK ордер отклоняется - попробуйте увеличить orderbook_level")
print("=" * 80)
