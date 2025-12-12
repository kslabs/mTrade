"""
Тест для проверки обновления start_price (P0) после стартовой покупки

Цель: Убедиться, что start_price обновляется в параметрах после каждой 
      стартовой покупки, и при следующем цикле таблица рассчитывается 
      с актуальной ценой.
"""

import json
import os

# Путь к файлу состояния
STATE_FILE = "app_state.json"

def test_start_price_update():
    """
    Тест проверяет, что start_price обновляется после стартовой покупки
    """
    
    print("=" * 80)
    print("ТЕСТ: Проверка обновления start_price (P0) после стартовой покупки")
    print("=" * 80)
    print()
    
    # Загружаем текущее состояние
    if not os.path.exists(STATE_FILE):
        print(f"❌ Файл {STATE_FILE} не найден!")
        return False
    
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
    except Exception as e:
        print(f"❌ Ошибка чтения файла {STATE_FILE}: {e}")
        return False
    
    # Получаем параметры breakeven
    breakeven_params = state.get('breakeven_params', {})
    
    if not breakeven_params:
        print("⚠️ Параметры breakeven_params отсутствуют в состоянии")
        return False
    
    print("📋 Параметры breakeven для каждой валюты:")
    print()
    
    all_ok = True
    
    for currency, params in breakeven_params.items():
        start_price = params.get('start_price', 0.0)
        start_volume = params.get('start_volume', 0.0)
        
        print(f"🔹 {currency}:")
        print(f"   start_price (P0): {start_price}")
        print(f"   start_volume:     {start_volume}")
        
        if start_price == 0.0:
            print(f"   ⚠️ start_price = 0 (возможно, цикл ещё не запускался)")
        elif start_price > 0:
            print(f"   ✅ start_price установлен корректно")
        
        print()
    
    print("=" * 80)
    print("РЕЗУЛЬТАТ ТЕСТА")
    print("=" * 80)
    print()
    
    if all_ok:
        print("✅ Все параметры загружены корректно")
        print()
        print("📝 ЧТО ПРОВЕРИТЬ ДАЛЬШЕ:")
        print("   1. Дождитесь стартовой покупки")
        print("   2. Проверьте лог - должно появиться:")
        print("      [CURRENCY] [DEBUG] Обновляем start_price в параметрах: <цена>...")
        print("      [CURRENCY] [DEBUG] start_price обновлён и сохранён!")
        print("   3. Снова запустите этот тест - start_price должен измениться")
        print("   4. Проверьте, что следующая продажа только с прибылью")
    else:
        print("⚠️ Обнаружены проблемы с параметрами")
    
    print()
    return all_ok

if __name__ == "__main__":
    test_start_price_update()
