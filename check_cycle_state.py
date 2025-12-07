"""
Проверка текущего состояния циклов после обновления
"""
import json
import os

STATE_FILE = "autotrader_cycles_state.json"

def check_state():
    print("=" * 70)
    print("ПРОВЕРКА СОСТОЯНИЯ ЦИКЛОВ")
    print("=" * 70)
    
    if not os.path.exists(STATE_FILE):
        print(f"\n❌ Файл {STATE_FILE} не найден")
        print("   Это нормально для первого запуска - файл будет создан автоматически")
        return
    
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    print(f"\n📊 Найдено валют: {len(data)}")
    print()
    
    for currency, cycle_data in data.items():
        print(f"┌─ {currency} " + "─" * (65 - len(currency)))
        
        # Новые поля (могут отсутствовать в старых файлах)
        cycle_id = cycle_data.get("cycle_id", "не указан (старый формат)")
        total_cycles = cycle_data.get("total_cycles_count", "не указан (старый формат)")
        
        print(f"│  Cycle ID:           {cycle_id}")
        print(f"│  Total Cycles:       {total_cycles}")
        print(f"│  Active:             {cycle_data.get('active', False)}")
        print(f"│  Active Step:        {cycle_data.get('active_step', -1)}")
        print(f"│  Start Price:        {cycle_data.get('start_price', 0.0)}")
        print(f"│  Base Volume:        {cycle_data.get('base_volume', 0.0)}")
        print(f"│  Invested USD:       {cycle_data.get('total_invested_usd', 0.0)}")
        print(f"│  Manual Pause:       {cycle_data.get('manual_pause', False)}")
        
        table = cycle_data.get('table', [])
        print(f"│  Table Steps:        {len(table)}")
        print(f"└{'─' * 68}")
        print()

if __name__ == "__main__":
    check_state()
