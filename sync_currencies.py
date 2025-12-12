#!/usr/bin/env python3
"""
Синхронизация валют в autotrader_cycles_state.json с разрешениями из app_state.json
"""

import json
import shutil
from datetime import datetime

print("\n" + "="*80)
print("СИНХРОНИЗАЦИЯ ВАЛЮТ АВТОТРЕЙДЕРА")
print("="*80 + "\n")

# 1. Загружаем текущие файлы
print("1. Загрузка файлов...")
print("-"*80)

try:
    with open("app_state.json", "r", encoding="utf-8") as f:
        app_state = json.load(f)
    print("   ✓ app_state.json загружен")
except Exception as e:
    print(f"   ✗ Ошибка загрузки app_state.json: {e}")
    exit(1)

try:
    with open("autotrader_cycles_state.json", "r", encoding="utf-8") as f:
        cycles_state = json.load(f)
    print("   ✓ autotrader_cycles_state.json загружен")
except Exception as e:
    print(f"   ✗ Ошибка загрузки autotrader_cycles_state.json: {e}")
    exit(1)

# 2. Получаем списки валют
print("\n2. Анализ валют...")
print("-"*80)

trading_perms = app_state.get("trading_permissions", {})
enabled_currencies = [curr for curr, enabled in trading_perms.items() if enabled]
existing_currencies = list(cycles_state.keys())

print(f"   Валют с разрешениями в app_state.json: {len(enabled_currencies)}")
print(f"   Валют в autotrader_cycles_state.json: {len(existing_currencies)}")

missing_currencies = [curr for curr in enabled_currencies if curr not in existing_currencies]
print(f"\n   Отсутствуют в автотрейдере: {len(missing_currencies)}")
for curr in sorted(missing_currencies):
    print(f"     - {curr}")

if not missing_currencies:
    print("\n✓ Все валюты уже синхронизированы!")
    exit(0)

# 3. Создаём резервную копию
print("\n3. Создание резервной копии...")
print("-"*80)

backup_name = f"autotrader_cycles_state.json.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
try:
    shutil.copy2("autotrader_cycles_state.json", backup_name)
    print(f"   ✓ Резервная копия создана: {backup_name}")
except Exception as e:
    print(f"   ✗ Ошибка создания резервной копии: {e}")
    exit(1)

# 4. Добавляем недостающие валюты
print("\n4. Добавление недостающих валют...")
print("-"*80)

# Шаблон для новой валюты (минимальная конфигурация)
def create_empty_cycle():
    return {
        "active": False,
        "active_step": -1,
        "last_buy_price": 0.0,
        "start_price": 0.0,
        "total_invested_usd": 0.0,
        "base_volume": 0.0,
        "table": [],
        "status": "idle",
        "manual_pause": False,
        "saved_at": datetime.now().timestamp()
    }

for curr in sorted(missing_currencies):
    cycles_state[curr] = create_empty_cycle()
    print(f"   ✓ Добавлена валюта: {curr}")

# 5. Сохраняем обновлённый файл
print("\n5. Сохранение изменений...")
print("-"*80)

try:
    with open("autotrader_cycles_state.json", "w", encoding="utf-8") as f:
        json.dump(cycles_state, f, indent=2, ensure_ascii=False)
    print(f"   ✓ Файл autotrader_cycles_state.json обновлён")
except Exception as e:
    print(f"   ✗ Ошибка сохранения: {e}")
    print(f"   Восстанавливаем из резервной копии...")
    shutil.copy2(backup_name, "autotrader_cycles_state.json")
    exit(1)

# 6. Проверка результата
print("\n6. Проверка результата...")
print("-"*80)

try:
    with open("autotrader_cycles_state.json", "r", encoding="utf-8") as f:
        updated_state = json.load(f)
    
    total_currencies = len(updated_state)
    print(f"   ✓ Всего валют в файле: {total_currencies}")
    print(f"\n   Список всех валют:")
    for curr in sorted(updated_state.keys()):
        status = "активен" if updated_state[curr].get("active") else "неактивен"
        step = updated_state[curr].get("active_step", -1)
        print(f"     - {curr}: {status}, шаг {step}")
    
except Exception as e:
    print(f"   ✗ Ошибка проверки: {e}")

print("\n" + "="*80)
print("СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
print("="*80)
print(f"""
РЕЗУЛЬТАТ:
  ✓ Добавлено валют: {len(missing_currencies)}
  ✓ Резервная копия: {backup_name}
  ✓ Всего валют: {len(cycles_state)}

ВАЖНО:
  Для применения изменений нужно ПЕРЕЗАПУСТИТЬ СЕРВЕР:
  1. Остановите mTrade.py (Ctrl+C)
  2. Запустите заново: python mTrade.py
  
  Автотрейдер загрузит обновлённый список валют при старте.
  
  Новые валюты будут в состоянии IDLE (неактивны).
  Автотрейдер начнёт их обрабатывать автоматически, если:
  - Разрешение на торговлю включено (уже включено в app_state.json)
  - Автотрейдер запущен и работает
  - Условия для старта цикла выполнены
""")
