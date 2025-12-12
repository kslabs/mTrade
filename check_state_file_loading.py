"""
Диагностика: проверка загрузки состояния из файла
Этот скрипт читает файл состояния и показывает, какие данные должны были загрузиться в память.
"""

import json
import os

STATE_FILE = "autotrader_cycles_state.json"

def check_state_file():
    """Проверить файл состояния и вывести данные для ETH"""
    print("=" * 80)
    print("ПРОВЕРКА ФАЙЛА СОСТОЯНИЯ")
    print("=" * 80)
    print()
    
    if not os.path.exists(STATE_FILE):
        print(f"❌ Файл {STATE_FILE} не найден!")
        return
    
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        print(f"✅ Файл загружен, найдено валют: {len(data)}")
        print()
        
        # Проверяем ETH
        if "ETH" not in data:
            print("❌ ETH не найден в файле состояния!")
            return
        
        eth_data = data["ETH"]
        print("=" * 80)
        print("ДАННЫЕ ETH ИЗ ФАЙЛА:")
        print("=" * 80)
        print(json.dumps(eth_data, indent=2, ensure_ascii=False))
        print()
        
        # Анализ данных
        print("=" * 80)
        print("АНАЛИЗ ДАННЫХ ETH:")
        print("=" * 80)
        print(f"active (bool): {eth_data.get('active')}")
        print(f"Тип active: {type(eth_data.get('active'))}")
        print(f"status: {eth_data.get('status')}")
        print(f"cycle_id: {eth_data.get('cycle_id')}")
        print(f"total_cycles_count: {eth_data.get('total_cycles_count')}")
        print(f"active_step: {eth_data.get('active_step')}")
        print(f"start_price: {eth_data.get('start_price')}")
        print(f"last_buy_price: {eth_data.get('last_buy_price')}")
        print(f"base_volume: {eth_data.get('base_volume')}")
        print(f"total_invested_usd: {eth_data.get('total_invested_usd')}")
        print(f"manual_pause: {eth_data.get('manual_pause')}")
        print()
        
        # Проверка логики загрузки
        print("=" * 80)
        print("ПРОВЕРКА ЛОГИКИ ЗАГРУЗКИ:")
        print("=" * 80)
        
        is_active = eth_data.get("active")
        print(f"eth_data.get('active') = {is_active}")
        print(f"bool(eth_data.get('active')) = {bool(is_active)}")
        
        if eth_data.get("active"):
            print("✅ Условие if cycle_data.get('active'): ВЫПОЛНИТСЯ")
            print("   Значит cycle.state должен быть = CycleState.ACTIVE")
            print("   И cycle.base_volume должен быть = {:.4f}".format(eth_data.get('base_volume', 0.0)))
        else:
            print("❌ Условие if cycle_data.get('active'): НЕ ВЫПОЛНИТСЯ")
            print("   Значит cycle.state останется = CycleState.IDLE")
        
    except Exception as e:
        print(f"❌ Ошибка при загрузке файла: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_state_file()
