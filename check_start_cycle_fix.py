"""
Быстрая проверка исправления: стартовая покупка только один раз
"""
import sys
from pathlib import Path

def check_fixes():
    """Проверяет наличие всех критических исправлений в коде"""
    
    autotrader_path = Path(__file__).parent / 'autotrader.py'
    
    if not autotrader_path.exists():
        print("❌ ОШИБКА: autotrader.py не найден!")
        return False
    
    with open(autotrader_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = {
        'Условный вызов в run()': 'if cycle.get(\'active\'):\n                            # Цикл АКТИВЕН - выполняем только усреднение',
        'Проверка base_volume в _try_start_cycle': 'base_volume = cycle.get(\'base_volume\', 0.0)',
        'Проверка start_price в _try_start_cycle': 'start_price = cycle.get(\'start_price\', 0.0)',
        'Проверка base_volume в _try_start_cycle_impl': '# === ФИНАЛЬНАЯ ПРОВЕРКА #2: base_volume должен быть 0 ===',
        'Проверка start_price в _try_start_cycle_impl': '# === ФИНАЛЬНАЯ ПРОВЕРКА #3: start_price должен быть 0 ===',
    }
    
    print("=" * 80)
    print("ПРОВЕРКА ИСПРАВЛЕНИЙ: Стартовая покупка только один раз")
    print("=" * 80)
    print()
    
    all_ok = True
    for check_name, check_pattern in checks.items():
        if check_pattern in content:
            print(f"✅ {check_name}")
        else:
            print(f"❌ {check_name}")
            all_ok = False
    
    print()
    print("=" * 80)
    
    if all_ok:
        print("✅ ВСЕ ИСПРАВЛЕНИЯ ПРИСУТСТВУЮТ В КОДЕ!")
        print()
        print("Следующие шаги:")
        print("1. Перезапустите автотрейдер: python mTrade.py")
        print("2. Проверьте логи на наличие множественных покупок")
        print("3. Проведите ручной тест: продажа → проверка стартовых покупок")
        print()
        return True
    else:
        print("❌ НЕКОТОРЫЕ ИСПРАВЛЕНИЯ ОТСУТСТВУЮТ!")
        print()
        print("КРИТИЧНО: Необходимо применить все исправления из FIX_START_CYCLE_ONLY_ONCE.md")
        print()
        return False

if __name__ == '__main__':
    success = check_fixes()
    sys.exit(0 if success else 1)
