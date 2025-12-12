"""
Быстрая проверка исправления target_delta_pct
"""

import json

def check_fix():
    print("=" * 80)
    print("ПРОВЕРКА ИСПРАВЛЕНИЯ target_delta_pct")
    print("=" * 80)
    
    # Загружаем состояние
    with open("autotrader_cycles_state.json", "r", encoding="utf-8") as f:
        state = json.load(f)
    
    if "XRP" not in state:
        print("❌ XRP не найден в состоянии")
        return
    
    xrp = state["XRP"]
    
    if not xrp.get("active"):
        print("❌ Цикл XRP не активен")
        return
    
    active_step = xrp.get("active_step", -1)
    table = xrp.get("table", [])
    
    if active_step < 0 or active_step >= len(table):
        print(f"❌ Некорректный active_step: {active_step}")
        return
    
    start_price = xrp.get("start_price", 0)
    if start_price <= 0:
        print("❌ start_price не установлен")
        return
    
    params_row = table[active_step]
    
    print(f"\n📊 XRP Cycle Info:")
    print(f"   Active Step: {active_step}")
    print(f"   Start Price: {start_price}")
    
    print(f"\n📋 Параметры шага {active_step}:")
    print(f"   breakeven_pct: {params_row.get('breakeven_pct')}")
    print(f"   target_delta_pct: {params_row.get('target_delta_pct')}")
    
    # СИМУЛИРУЕМ ИСПРАВЛЕННУЮ ЛОГИКУ
    breakeven_pct = params_row.get('breakeven_pct', 0)
    target_delta_pct = params_row.get('target_delta_pct', 0)
    
    # СТАРАЯ ЛОГИКА
    old_required = float(breakeven_pct)
    
    # НОВАЯ ЛОГИКА
    new_required = float(target_delta_pct if target_delta_pct else breakeven_pct)
    
    print(f"\n🔧 ЛОГИКА ПОРОГА ПРОДАЖИ:")
    print(f"   СТАРАЯ (breakeven_pct): {old_required:.4f}%")
    print(f"   НОВАЯ (target_delta_pct): {new_required:.4f}%")
    
    # Текущая цена (примерная)
    current_price = 2.042
    current_growth = ((current_price - start_price) / start_price) * 100.0
    
    print(f"\n💰 ТЕКУЩЕЕ СОСТОЯНИЕ:")
    print(f"   Текущая цена: {current_price}")
    print(f"   Текущий рост: {current_growth:.4f}%")
    
    print(f"\n🎯 ПРОВЕРКА УСЛОВИЯ ПРОДАЖИ:")
    print(f"   СТАРАЯ логика: {current_growth:.4f}% >= {old_required:.4f}% ? {'✅ ДА' if current_growth >= old_required else '❌ НЕТ'}")
    print(f"   НОВАЯ логика: {current_growth:.4f}% >= {new_required:.4f}% ? {'✅ ДА' if current_growth >= new_required else '❌ НЕТ'}")
    
    if current_growth >= new_required and current_growth >= old_required:
        print(f"\n✅ РЕЗУЛЬТАТ: Продажа ДОЛЖНА происходить (оба условия выполнены)")
    elif current_growth >= new_required:
        print(f"\n🎉 РЕЗУЛЬТАТ: С НОВОЙ логикой продажа БУДЕТ происходить!")
        print(f"   (Старая логика бы НЕ продала)")
    elif current_growth >= old_required:
        print(f"\n⚠️ РЕЗУЛЬТАТ: Только СТАРАЯ логика бы продала (что странно)")
    else:
        print(f"\n❌ РЕЗУЛЬТАТ: Рост недостаточен для продажи")
    
    print("\n" + "=" * 80)
    print("ВЫВОД:")
    print("=" * 80)
    if old_required == 0 and new_required > 0:
        print("✅ ИСПРАВЛЕНИЕ КРИТИЧЕСКИ ВАЖНО!")
        print(f"   Без него продажа требовала {old_required}% (невозможно из-за комиссий)")
        print(f"   Теперь продажа требует {new_required}% (реалистично)")
    elif old_required != new_required:
        print(f"✅ Исправление изменяет порог с {old_required}% на {new_required}%")
    else:
        print(f"ℹ️  Для этого шага оба значения одинаковы: {old_required}%")

if __name__ == "__main__":
    check_fix()
