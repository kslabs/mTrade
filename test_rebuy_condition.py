# Быстрая проверка логики докупки ETH

# Данные из UI
current_price = 3181.42
last_buy_price = 3208.58
rebuy_trigger_pct = 0.73  # Из "След. покупка: 3,185.16" → падение 0.73%

# Расчёт порога докупки
rebuy_threshold = last_buy_price * (1.0 - rebuy_trigger_pct / 100.0)

print(f"Текущая цена: {current_price}")
print(f"Последняя покупка: {last_buy_price}")
print(f"Порог докупки (-{rebuy_trigger_pct}%): {rebuy_threshold:.8f}")
print(f"Условие: {current_price} < {rebuy_threshold} ?")
print(f"Результат: {current_price < rebuy_threshold}")

if current_price < rebuy_threshold:
    print(f"✅ Условие докупки ВЫПОЛНЕНО! Падение: {((last_buy_price - current_price) / last_buy_price * 100):.2f}%")
else:
    print(f"❌ Условие докупки НЕ ВЫПОЛНЕНО! Разница: {current_price - rebuy_threshold:.8f}")
