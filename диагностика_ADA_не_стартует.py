"""
Диагностика проблемы со стартом торговли ADA
"""
import json
import os

print("=" * 80)
print("ДИАГНОСТИКА: Почему ADA не стартует торговлю?")
print("=" * 80)

# 1. Проверяем state-файл ADA
state_file = "cycle_state_ADA.json"
if os.path.exists(state_file):
    print(f"\n✅ Найден файл состояния: {state_file}")
    with open(state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)
    
    print(f"\n📊 Состояние цикла ADA:")
    print(f"   State: {state.get('state', 'UNKNOWN')}")
    print(f"   Active: {state.get('active', False)}")
    print(f"   Manual Pause: {state.get('manual_pause', False)}")
    print(f"   Active Step: {state.get('active_step', -1)}")
    print(f"   Base Volume: {state.get('base_volume', 0)}")
    print(f"   Total Invested: {state.get('total_invested_usd', 0)}")
    print(f"   Last Buy Price: {state.get('last_buy_price', 0)}")
    
    if state.get('manual_pause'):
        print(f"\n🔴 ПРОБЛЕМА: Цикл ADA на РУЧНОЙ ПАУЗЕ!")
        print(f"   Необходимо нажать кнопку 'Старт цикла' на фронтенде")
else:
    print(f"\n⚠️ Файл состояния НЕ найден: {state_file}")
    print(f"   Цикл будет создан автоматически при первом запуске")

# 2. Проверяем разрешения торговли
ui_state_file = "ui_state.json"
if os.path.exists(ui_state_file):
    print(f"\n✅ Найден файл UI состояния: {ui_state_file}")
    with open(ui_state_file, 'r', encoding='utf-8') as f:
        ui_state = json.load(f)
    
    enabled = ui_state.get('enabled_currencies', {})
    ada_enabled = enabled.get('ADA', False)
    
    print(f"\n📊 Разрешения торговли:")
    print(f"   ADA: {'✅ Разрешена' if ada_enabled else '🔴 ЗАПРЕЩЕНА'}")
    
    if not ada_enabled:
        print(f"\n🔴 ПРОБЛЕМА: Торговля ADA ЗАПРЕЩЕНА!")
        print(f"   Необходимо включить торговлю на фронтенде")
else:
    print(f"\n⚠️ Файл UI состояния НЕ найден: {ui_state_file}")

# 3. Проверяем логи (последние 50 строк)
print(f"\n📋 Последние логи ADA:")
print("=" * 80)
try:
    with open('mTrade.log', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        ada_lines = [l for l in lines if 'ADA' in l][-50:]
        for line in ada_lines[-10:]:
            print(line.strip())
except Exception as e:
    print(f"⚠️ Не удалось прочитать логи: {e}")

print("\n" + "=" * 80)
print("РЕКОМЕНДАЦИИ:")
print("=" * 80)

recommendations = []

if os.path.exists(state_file):
    with open(state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)
    
    if state.get('manual_pause'):
        recommendations.append("1. Нажмите кнопку 'Старт цикла' для ADA на фронтенде")
    
    if state.get('base_volume', 0) > 0:
        recommendations.append("2. Дождитесь продажи остатков ADA (ордер создан, ждём исполнения)")

if os.path.exists(ui_state_file):
    with open(ui_state_file, 'r', encoding='utf-8') as f:
        ui_state = json.load(f)
    
    if not ui_state.get('enabled_currencies', {}).get('ADA', False):
        recommendations.append("3. Включите торговлю для ADA на фронтенде (галочка)")

if not recommendations:
    recommendations.append("1. Проверьте баланс USDT (достаточно ли для покупки?)")
    recommendations.append("2. Проверьте параметры торговли ADA (start_volume, start_price)")
    recommendations.append("3. Проверьте консоль сервера на наличие ошибок")

for rec in recommendations:
    print(f"   {rec}")

print("\n" + "=" * 80)
