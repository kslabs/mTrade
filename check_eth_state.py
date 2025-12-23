"""
Диагностика состояния ETH цикла
Проверяет расхождение между файлом и памятью
"""
import json

# Читаем файл состояния
with open("autotrader_cycles_state.json", "r", encoding="utf-8") as f:
    state = json.load(f)

eth_state = state.get("ETH", {})

print("=" * 60)
print("СОСТОЯНИЕ ETH В ФАЙЛЕ autotrader_cycles_state.json")
print("=" * 60)
print(f"active: {eth_state.get('active')}")
print(f"cycle_id: {eth_state.get('cycle_id')}")
print(f"active_step: {eth_state.get('active_step')}")
print(f"start_price: {eth_state.get('start_price')}")
print(f"last_buy_price: {eth_state.get('last_buy_price')}")
print(f"total_invested_usd: {eth_state.get('total_invested_usd')}")
print(f"base_volume: {eth_state.get('base_volume')}")
print(f"table rows: {len(eth_state.get('table', []))}")
print()

if eth_state.get('table'):
    print("Первая строка таблицы:")
    first_row = eth_state['table'][0]
    print(f"  step: {first_row.get('step')}")
    print(f"  rate: {first_row.get('rate')}")
    print(f"  decrease_step_pct: {first_row.get('decrease_step_pct')}")
    print()

print("=" * 60)
print("ОЖИДАЕМОЕ СОСТОЯНИЕ (из логов):")
print("=" * 60)
print("active: True")
print("cycle_id: 50")
print("active_step: 1")
print("start_price: 3208.58")
print("last_buy_price: 3182.26")
print("total_invested_usd: 23.63")
print("base_volume: 0.0074")
print()

print("=" * 60)
print("ПРОБЛЕМА:")
print("=" * 60)
if eth_state.get('active_step') == -1:
    print("❌ active_step = -1 (должно быть 1)")
    print("   Цикл сброшен в IDLE, хотя active=True")
    print()
    print("ПРИЧИНА:")
    print("   После докупки состояние не сохранилось правильно")
    print("   Возможно, произошла ошибка при сохранении или")
    print("   цикл был сброшен другим процессом")
    print()
    print("РЕШЕНИЕ:")
    print("   1. Перезапустить сервер")
    print("   2. Проверить, что после докупки вызывается self._save_state()")
    print("   3. Убедиться, что нет конкурирующих процессов, изменяющих файл")
