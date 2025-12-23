#!/usr/bin/env python3
"""
Скрипт для ручного сброса цикла XRP

ИСПОЛЬЗОВАНИЕ:
    python reset_xrp_cycle.py

ПРИЧИНА СБРОСА:
    Продажа XRP произошла на бирже, но автотрейдер не зафиксировал это.
    В результате:
    - Баланс XRP: ~0.00026200 (почти 0)
    - Состояние цикла: active
    - Объём в состоянии: 4.892 XRP
    
    Это несоответствие блокирует автотрейдер.
"""

import json
from datetime import datetime
import shutil

print("=" * 70)
print("  СКРИПТ РУЧНОГО СБРОСА ЦИКЛА XRP")
print("=" * 70)
print()

# Создаём резервную копию
backup_file = f"autotrader_cycles_state.json.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
shutil.copy('autotrader_cycles_state.json', backup_file)
print(f"✅ Резервная копия создана: {backup_file}")
print()

# Загружаем состояние
with open('autotrader_cycles_state.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

xrp = data.get('XRP', {})

print("ТЕКУЩЕЕ СОСТОЯНИЕ XRP:")
print(f"  Status: {xrp.get('status')}")
print(f"  Start Price: {xrp.get('start_price')}")
print(f"  Base Volume: {xrp.get('base_volume')}")
print(f"  Total Invested: {xrp.get('total_invested_usd')}")
print(f"  Cycle ID: {xrp.get('cycle_id')}")
print(f"  Total Cycles: {xrp.get('total_cycles_count')}")
print()

# Подтверждение
print("⚠️  ВНИМАНИЕ!")
print("   Этот скрипт СБРОСИТ цикл XRP в состояние IDLE.")
print("   Это означает:")
print("   - Текущий цикл будет считаться завершённым")
print("   - Счётчик циклов будет увеличен на 1")
print("   - Все параметры активного цикла будут сброшены")
print("   - Автотрейдер начнёт искать новую точку входа (покупки)")
print()

confirmation = input("Вы уверены? Введите 'ДА' для продолжения: ")

if confirmation != 'ДА':
    print("❌ Отменено пользователем")
    exit(0)

print()
print("Выполняется сброс...")
print()

# Сбрасываем цикл
xrp['status'] = 'idle'
xrp['state'] = 'idle'
xrp['start_price'] = 0.0
xrp['last_buy_price'] = 0.0
xrp['total_invested_usd'] = 0.0
xrp['base_volume'] = 0.0
xrp['active_step'] = -1
xrp['cycle_started_at'] = 0.0
xrp['last_action_at'] = datetime.now().timestamp()
xrp['manual_pause'] = False
xrp['table'] = []

# Увеличиваем счётчик завершённых циклов
if 'total_cycles_count' in xrp:
    xrp['total_cycles_count'] += 1
    print(f"✅ Цикл #{xrp.get('cycle_id')} завершён!")
    print(f"✅ Всего завершённых циклов: {xrp['total_cycles_count']}")

# Сбрасываем флаги (если есть)
if '_buying_in_progress' in xrp:
    xrp['_buying_in_progress'] = False
if '_selling_in_progress' in xrp:
    xrp['_selling_in_progress'] = False

# Сохраняем изменения
data['XRP'] = xrp

with open('autotrader_cycles_state.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print()
print("✅ Цикл XRP сброшен в состояние IDLE")
print()

print("НОВОЕ СОСТОЯНИЕ XRP:")
print(f"  Status: {xrp.get('status')}")
print(f"  Start Price: {xrp.get('start_price')}")
print(f"  Base Volume: {xrp.get('base_volume')}")
print(f"  Total Invested: {xrp.get('total_invested_usd')}")
print(f"  Total Cycles: {xrp.get('total_cycles_count')}")
print()

print("=" * 70)
print("  ЧТО ДЕЛАТЬ ДАЛЬШЕ")
print("=" * 70)
print()
print("1. Проверьте, что автотрейдер работает:")
print("   • Должны появиться логи мониторинга цен")
print("   • При падении цены начнётся новая покупка")
print()
print("2. Если автотрейдер НЕ запущен:")
print("   • Запустите: python autotrader_v2.py")
print()
print("3. Если проблема повторится:")
print("   • Проверьте логи автотрейдера")
print("   • Проверьте, что LIMIT-ордера создаются корректно")
print("   • Проверьте, что автотрейдер правильно обрабатывает")
print("     статус LIMIT-ордеров (closed/open)")
print()
print("=" * 70)
