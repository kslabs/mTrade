"""
Восстановление состояния ETH после докупки
Исправляет файл autotrader_cycles_state.json
"""
import json
from datetime import datetime

# Читаем файл
with open("autotrader_cycles_state.json", "r", encoding="utf-8") as f:
    state = json.load(f)

# Исправляем ETH (данные из логов докупки)
state["ETH"]["active"] = True
state["ETH"]["active_step"] = 1  # После первой докупки
state["ETH"]["start_price"] = 3208.58  # Первая покупка
state["ETH"]["last_buy_price"] = 3182.26  # Последняя докупка
state["ETH"]["total_invested_usd"] = 23.630316  # 9.946598 + 13.683718
state["ETH"]["base_volume"] = 0.0074  # 0.0031 + 0.0043
state["ETH"]["saved_at"] = datetime.now().timestamp()

print("Исправленное состояние ETH:")
print(json.dumps(state["ETH"], indent=2, ensure_ascii=False))

# Сохраняем
with open("autotrader_cycles_state.json", "w", encoding="utf-8") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)

print("\n✅ Файл autotrader_cycles_state.json обновлён!")
