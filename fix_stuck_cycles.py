"""
Скрипт для исправления "зависших" циклов в autotrader_cycles_state.json
Сбрасывает циклы с active=True но base_volume=0 (цикл стартовал, но покупки не было)
"""
import json
import time
from pathlib import Path

STATE_FILE = Path(__file__).parent / 'autotrader_cycles_state.json'

def fix_stuck_cycles():
    """Исправляет зависшие циклы"""
    if not STATE_FILE.exists():
        print(f"❌ Файл {STATE_FILE} не найден")
        return
    
    # Читаем текущее состояние
    with open(STATE_FILE, 'r', encoding='utf-8') as f:
        cycles = json.load(f)
    
    print("=" * 80)
    print("🔍 ПРОВЕРКА ЦИКЛОВ НА ЗАВИСШИЕ СОСТОЯНИЯ")
    print("=" * 80)
    
    fixed_count = 0
    current_time = time.time()
    
    for base, cycle in cycles.items():
        active = cycle.get('active', False)
        base_volume = float(cycle.get('base_volume', 0))
        
        # Проверяем: цикл активен, но базовой валюты нет или очень мало
        if active and base_volume < 1e-8:
            print(f"\n⚠️  Найден зависший цикл: {base}")
            print(f"   - active: {active}")
            print(f"   - base_volume: {base_volume}")
            print(f"   - active_step: {cycle.get('active_step', -1)}")
            print(f"   РЕШЕНИЕ: Сбрасываем цикл")
            
            # Сбрасываем цикл
            cycle['active'] = False
            cycle['active_step'] = -1
            cycle['last_buy_price'] = 0.0
            cycle['start_price'] = 0.0
            cycle['total_invested_usd'] = 0.0
            cycle['base_volume'] = 0.0
            cycle['pending_start'] = False
            cycle['last_sell_time'] = current_time
            cycle['last_start_attempt'] = 0
            cycle['saved_at'] = current_time  # КРИТИЧНО: Добавляем метку времени сохранения
            
            fixed_count += 1
            print(f"   ✅ Цикл {base} сброшен")
    
    if fixed_count == 0:
        print("\n✅ Зависших циклов не найдено")
        return
    
    # Создаём резервную копию
    backup_file = STATE_FILE.with_suffix('.json.backup_fix')
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(cycles, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Создана резервная копия: {backup_file}")
    
    # Сохраняем исправленное состояние
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cycles, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 80)
    print(f"✅ ИСПРАВЛЕНО ЦИКЛОВ: {fixed_count}")
    print("=" * 80)
    print("\n🔄 СЛЕДУЮЩИЙ ШАГ: Перезапустите сервер")
    print("   python stop.py")
    print("   python mTrade.py")

if __name__ == '__main__':
    fix_stuck_cycles()
