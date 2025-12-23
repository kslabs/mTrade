"""
Простая проверка: расчёт required price для XRP5L
"""

# Данные из интерфейса
base = "XRP5L"
current_price = 0.04697
start_price = 0.0467  # P0
be_price = 0.0467      # BE
last_buy_price = 0.0467  # Последняя покупка
profit_pct = 0.45  # Из параметров

print(f"\n{'='*60}")
print(f"РАСЧЁТ УСЛОВИЯ ПРОДАЖИ: {base}")
print(f"{'='*60}\n")

print(f"📊 ИСХОДНЫЕ ДАННЫЕ:")
print(f"   Current price: {current_price:.8f}")
print(f"   Start price (P0): {start_price:.8f}")
print(f"   Breakeven (BE): {be_price:.8f}")
print(f"   Last buy price: {last_buy_price:.8f}")
print(f"   Profit %: {profit_pct:.2f}%")

# Рост от P0
growth_from_p0 = ((current_price - start_price) / start_price) * 100
print(f"\n📈 ТЕКУЩИЙ РОСТ:")
print(f"   От P0: {growth_from_p0:.2f}%")
print(f"   От last buy: {growth_from_p0:.2f}% (т.к. last_buy = P0 на шаге 0)")

# Требуемая цена для продажи (от last_buy_price)
required_price = last_buy_price * (1 + profit_pct / 100.0)
print(f"\n🎯 УСЛОВИЕ ПРОДАЖИ:")
print(f"   Required price: {required_price:.8f}")
print(f"   Формула: last_buy * (1 + profit% / 100)")
print(f"   = {last_buy_price:.8f} * (1 + {profit_pct:.2f} / 100)")
print(f"   = {last_buy_price:.8f} * {1 + profit_pct / 100:.6f}")
print(f"   = {required_price:.8f}")

print(f"\n✅ ПРОВЕРКА:")
print(f"   {current_price:.8f} >= {required_price:.8f} ?")

if current_price >= required_price:
    profit = ((current_price - required_price) / required_price) * 100
    print(f"   ✅ ДА! Цена выше на {profit:.4f}%")
    print(f"\n💡 ПРОДАЖА ДОЛЖНА ПРОИЗОЙТИ!")
    print(f"   Если не происходит, проверьте:")
    print(f"      1. Цену в стакане (orderbook_price)")
    print(f"      2. Логи сервера (поиск XRP5L)")
    print(f"      3. Флаг _selling_in_progress")
else:
    diff = required_price - current_price
    diff_pct = (diff / required_price) * 100
    print(f"   ❌ НЕТ! Не хватает {diff:.8f} ({diff_pct:.2f}%)")
    print(f"\n💡 ПРОДАЖА НЕ ПРОИЗОЙДЁТ")
    print(f"   Цена должна вырасти ещё на {diff_pct:.2f}%")

print(f"\n{'='*60}\n")
