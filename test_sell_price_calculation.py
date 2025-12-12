#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест расчета целевой цены продажи
"""

def test_sell_price_calculation():
    """
    Проверяем правильность расчета целевой цены продажи
    """
    
    # Пример данных из логов ETH
    start_price = 3408.5  # Стартовая цена
    
    # Шаг 0 (первая покупка)
    step_0_rate = 3408.5  # Расчетный курс = стартовая цена
    step_0_breakeven = 3408.5  # Цена безубыточности = стартовая цена (без комиссий для упрощения)
    step_0_target_delta_pct = 0.15  # Целевая дельта +0.15%
    
    # СТАРАЯ (неправильная) формула:
    old_target_sell_price = step_0_breakeven * (1 + step_0_target_delta_pct / 100.0)
    
    # НОВАЯ (правильная) формула:
    new_target_sell_price = step_0_rate * (1 + step_0_target_delta_pct / 100.0)
    
    print("=" * 80)
    print("Шаг 0 (первая покупка)")
    print("-" * 80)
    print(f"Стартовая цена: {start_price}")
    print(f"Расчетный курс шага: {step_0_rate}")
    print(f"Цена безубыточности: {step_0_breakeven}")
    print(f"Целевая дельта: +{step_0_target_delta_pct}%")
    print()
    print(f"СТАРАЯ формула (breakeven * (1 + delta%)): {old_target_sell_price:.2f}")
    print(f"НОВАЯ формула (rate * (1 + delta%)): {new_target_sell_price:.2f}")
    print()
    
    # Пример данных для шага 1 (докупка)
    step_1_rate = 3388.0  # Расчетный курс после снижения -0.60%
    step_1_breakeven = 3398.25  # Средняя цена покупки (взвешенная)
    step_1_target_delta_pct = 0.41  # Целевая дельта (выше, чтобы покрыть убыток)
    
    # СТАРАЯ (неправильная) формула:
    old_target_sell_price_1 = step_1_breakeven * (1 + step_1_target_delta_pct / 100.0)
    
    # НОВАЯ (правильная) формула:
    new_target_sell_price_1 = step_1_rate * (1 + step_1_target_delta_pct / 100.0)
    
    print("=" * 80)
    print("Шаг 1 (докупка после снижения)")
    print("-" * 80)
    print(f"Расчетный курс шага: {step_1_rate}")
    print(f"Цена безубыточности: {step_1_breakeven}")
    print(f"Целевая дельта: +{step_1_target_delta_pct}%")
    print()
    print(f"СТАРАЯ формула (breakeven * (1 + delta%)): {old_target_sell_price_1:.2f}")
    print(f"НОВАЯ формула (rate * (1 + delta%)): {new_target_sell_price_1:.2f}")
    print()
    
    # Проверка защиты: целевая цена не должна быть ниже безубыточности
    if new_target_sell_price_1 < step_1_breakeven:
        print(f"⚠️  ЗАЩИТА: Целевая цена ({new_target_sell_price_1:.2f}) < Безубыточность ({step_1_breakeven:.2f})")
        print(f"   Корректируем до: {step_1_breakeven:.2f}")
        new_target_sell_price_1 = step_1_breakeven
    else:
        print(f"✅ OK: Целевая цена ({new_target_sell_price_1:.2f}) >= Безубыточность ({step_1_breakeven:.2f})")
    
    print()
    
    # Реальный пример из логов (продажа с убытком)
    print("=" * 80)
    print("Реальный случай из логов (продажа с убытком)")
    print("-" * 80)
    
    eth_start = 3408.5
    eth_current = 3406.78  # Текущая цена (ниже стартовой)
    eth_rate_0 = 3408.5
    eth_breakeven_0 = 3408.5
    eth_target_delta = 0.15
    
    # СТАРАЯ формула (неправильная):
    old_target = eth_breakeven_0 * (1 + eth_target_delta / 100.0)
    
    # НОВАЯ формула (правильная):
    new_target = eth_rate_0 * (1 + eth_target_delta / 100.0)
    
    print(f"Стартовая цена: {eth_start}")
    print(f"Текущая цена: {eth_current}")
    print(f"Расчетный курс: {eth_rate_0}")
    print(f"Безубыточность: {eth_breakeven_0}")
    print(f"Целевая дельта: +{eth_target_delta}%")
    print()
    print(f"СТАРАЯ целевая цена: {old_target:.2f}")
    print(f"НОВАЯ целевая цена: {new_target:.2f}")
    print()
    
    if eth_current >= old_target:
        print(f"❌ СТАРАЯ логика: Продажа произошла бы (current {eth_current} >= target {old_target:.2f})")
        delta_pct = ((eth_current - eth_start) / eth_start) * 100
        print(f"   Дельта от старта: {delta_pct:.2f}% (УБЫТОК!)")
    else:
        print(f"✅ СТАРАЯ логика: Продажа НЕ произошла бы (current {eth_current} < target {old_target:.2f})")
    
    print()
    
    if eth_current >= new_target:
        print(f"✅ НОВАЯ логика: Продажа произойдет (current {eth_current} >= target {new_target:.2f})")
    else:
        print(f"✅ НОВАЯ логика: Продажа НЕ произойдет (current {eth_current} < target {new_target:.2f})")
        delta_needed = ((new_target - eth_current) / eth_current) * 100
        print(f"   Нужен рост еще на {delta_needed:.2f}%")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    test_sell_price_calculation()
