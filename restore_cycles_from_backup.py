"""
Скрипт для восстановления ETH и XRP в файле состояния
"""
import json
import time
from pathlib import Path

STATE_FILE = Path(__file__).parent / 'autotrader_cycles_state.json'
BACKUP_FILE = Path(__file__).parent / 'autotrader_cycles_state.json.backup_fix'

def restore_missing_cycles():
    """Восстанавливает отсутствующие циклы из резервной копии"""
    if not BACKUP_FILE.exists():
        print(f"❌ Резервная копия {BACKUP_FILE} не найдена")
        return
    
    if not STATE_FILE.exists():
        print(f"❌ Файл {STATE_FILE} не найден")
        return
    
    # Читаем текущее состояние
    with open(STATE_FILE, 'r', encoding='utf-8') as f:
        current_cycles = json.load(f)
    
    # Читаем резервную копию
    with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
        backup_cycles = json.load(f)
    
    print("=" * 80)
    print("🔧 ВОССТАНОВЛЕНИЕ ОТСУТСТВУЮЩИХ ЦИКЛОВ")
    print("=" * 80)
    
    restored_count = 0
    current_time = time.time()
    
    # Проверяем, каких циклов нет в текущем файле
    for base, cycle in backup_cycles.items():
        if base not in current_cycles:
            print(f"\n⚠️  Восстанавливаем цикл: {base}")
            print(f"   - active: {cycle.get('active', False)}")
            print(f"   - base_volume: {cycle.get('base_volume', 0)}")
            
            # Обновляем saved_at на текущее время
            cycle['saved_at'] = current_time
            
            # Добавляем в текущее состояние
            current_cycles[base] = cycle
            restored_count += 1
            print(f"   ✅ Цикл {base} восстановлен")
    
    if restored_count == 0:
        print("\n✅ Все циклы присутствуют в файле")
        return
    
    # Сохраняем обновлённое состояние
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(current_cycles, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 80)
    print(f"✅ ВОССТАНОВЛЕНО ЦИКЛОВ: {restored_count}")
    print("=" * 80)
    print("\n🔄 СЛЕДУЮЩИЙ ШАГ: Перезапустите сервер")
    print("   python stop.py")
    print("   python mTrade.py")

if __name__ == '__main__':
    restore_missing_cycles()
