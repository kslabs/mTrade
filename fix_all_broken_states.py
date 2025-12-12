"""
Исправление состояния ВСЕХ валют с противоречивыми данными

ПРОБЛЕМА: active=true, но active_step=-1 (нет данных о покупках)
РЕШЕНИЕ: Устанавливаем active=false для таких валют
"""
import json
from datetime import datetime

# Читаем файл
with open("autotrader_cycles_state.json", "r", encoding="utf-8") as f:
    state = json.load(f)

broken_currencies = []
fixed_count = 0

print("=" * 60)
print("ПОИСК ВАЛЮТ С ПРОТИВОРЕЧИВЫМ СОСТОЯНИЕМ")
print("=" * 60)

for currency, data in state.items():
    active = data.get("active", False)
    active_step = data.get("active_step", -1)
    
    # Проверяем противоречие: active=true, но active_step=-1
    if active and active_step == -1:
        broken_currencies.append(currency)
        print(f"\n❌ {currency}:")
        print(f"   active: {active}")
        print(f"   active_step: {active_step}")
        print(f"   base_volume: {data.get('base_volume', 0)}")
        print(f"   total_invested_usd: {data.get('total_invested_usd', 0)}")
        print(f"   → ТРЕБУЕТСЯ ИСПРАВЛЕНИЕ")

print(f"\n{'=' * 60}")
print(f"Найдено валют с противоречиями: {len(broken_currencies)}")
print(f"{'=' * 60}\n")

if not broken_currencies:
    print("✅ Все валюты в порядке!")
else:
    print(f"Исправляем {len(broken_currencies)} валют...\n")
    
    for currency in broken_currencies:
        # Исправляем: устанавливаем active=false
        state[currency]["active"] = False
        state[currency]["status"] = "idle"
        state[currency]["saved_at"] = datetime.now().timestamp()
        fixed_count += 1
        
        print(f"✅ {currency}: active=false установлен")
    
    # Сохраняем исправленное состояние
    with open("autotrader_cycles_state.json", "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'=' * 60}")
    print(f"✅ Исправлено валют: {fixed_count}")
    print(f"✅ Файл autotrader_cycles_state.json обновлён!")
    print(f"{'=' * 60}")
    
    print("\nИСПРАВЛЕННЫЕ ВАЛЮТЫ:")
    for currency in broken_currencies:
        print(f"  - {currency}: active=false (был active=true с active_step=-1)")
