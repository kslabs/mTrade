"""
Диагностика условий продажи для SUI
Проверяет, почему не происходит продажа
"""
import json

# Данные с веб-страницы
current_price = 1.5717
start_price = 1.5482
current_step = 1

# Читаем файл состояния
with open("autotrader_cycles_state.json", "r", encoding="utf-8") as f:
    state = json.load(f)

sui_state = state.get("SUI", {})

print("=" * 80)
print("ДИАГНОСТИКА УСЛОВИЙ ПРОДАЖИ SUI")
print("=" * 80)
print()

print("📊 ДАННЫЕ С ВЕБ-СТРАНИЦЫ:")
print(f"  Текущая цена: {current_price}")
print(f"  Стартовая (P0): {start_price}")
print(f"  Текущий шаг: {current_step}")
print(f"  Рост от P0: {((current_price - start_price) / start_price * 100):.2f}%")
print()

print("📁 ДАННЫЕ ИЗ ФАЙЛА СОСТОЯНИЯ:")
print(f"  active: {sui_state.get('active')}")
print(f"  active_step: {sui_state.get('active_step')}")
print(f"  start_price: {sui_state.get('start_price')}")
print(f"  last_buy_price: {sui_state.get('last_buy_price')}")
print(f"  total_invested_usd: {sui_state.get('total_invested_usd')}")
print(f"  base_volume: {sui_state.get('base_volume')}")
print()

# Проверяем таблицу
table = sui_state.get('table', [])
if table and len(table) > current_step:
    step_data = table[current_step]
    required_growth_pct = step_data.get('breakeven_pct', 0)
    breakeven_price = step_data.get('breakeven_price', 0)
    
    print(f"📋 ДАННЫЕ ИЗ ТАБЛИЦЫ (шаг {current_step}):")
    print(f"  breakeven_price: {breakeven_price}")
    print(f"  breakeven_pct: {required_growth_pct}%")
    print(f"  target_delta_pct: {step_data.get('target_delta_pct')}%")
    print()
    
    # Рассчитываем текущий рост
    file_start_price = sui_state.get('start_price', 0)
    if file_start_price > 0:
        current_growth = ((current_price - file_start_price) / file_start_price) * 100.0
        
        print("🔍 ПРОВЕРКА УСЛОВИЯ ПРОДАЖИ:")
        print(f"  Start price (из файла): {file_start_price}")
        print(f"  Current price: {current_price}")
        print(f"  Current growth: {current_growth:.4f}%")
        print(f"  Required growth: {required_growth_pct:.4f}%")
        print(f"  Условие: {current_growth:.4f}% >= {required_growth_pct:.4f}% ?")
        print()
        
        if current_growth >= required_growth_pct:
            print("✅ УСЛОВИЕ ВЫПОЛНЕНО! Продажа должна произойти!")
            print()
            print("🤔 ВОЗМОЖНЫЕ ПРИЧИНЫ, ПОЧЕМУ НЕ ПРОДАЁТ:")
            print("  1. Автотрейдер не работает (остановлен)")
            print("  2. Флаг _selling_in_progress установлен (продажа в процессе)")
            print("  3. Есть открытые SELL ордера")
            print("  4. FOK ордер постоянно отклоняется (цена из стакана слишком высокая)")
            print("  5. Цена из стакана (bids[0]) ниже breakeven_price")
        else:
            print("❌ УСЛОВИЕ НЕ ВЫПОЛНЕНО!")
            print(f"  Не хватает роста: {required_growth_pct - current_growth:.4f}%")
            print(f"  Нужна цена: {file_start_price * (1 + required_growth_pct / 100):.4f}")
else:
    print("❌ Таблица не найдена или некорректный шаг!")
