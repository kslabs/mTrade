"""Тест прямого вызова get_cycle_info без HTTP"""
import sys
import time

# Импортируем главный модуль
import mTrade

print("="*70)
print("ПРЯМОЙ ТЕСТ get_cycle_info()")
print("="*70)

# Получаем AUTO_TRADER
AUTO_TRADER = mTrade.AUTO_TRADER

if AUTO_TRADER:
    print(f"\n✅ AUTO_TRADER найден: {AUTO_TRADER}")
    print(f"   Running: {AUTO_TRADER.running}")
    print(f"   Cycles count: {len(AUTO_TRADER.cycles)}")
    
    # Проверяем ETH напрямую
    print(f"\n🔍 Прямая проверка ETH в памяти:")
    eth_cycle = AUTO_TRADER.cycles.get('ETH')
    if eth_cycle:
        print(f"   ✅ ETH цикл найден в памяти")
        print(f"   State: {eth_cycle.state}")
        print(f"   Active: {eth_cycle.is_active()}")
        print(f"   Cycle ID: {eth_cycle.cycle_id}")
        print(f"   Base Volume: {eth_cycle.base_volume}")
        print(f"   Start Price: {eth_cycle.start_price}")
    else:
        print(f"   ❌ ETH цикл НЕ найден в памяти!")
    
    # Вызываем get_cycle_info
    print(f"\n📞 Вызов AUTO_TRADER.get_cycle_info('ETH'):")
    result = AUTO_TRADER.get_cycle_info('ETH')
    
    if result:
        print(f"   ✅ Результат получен:")
        print(f"   State: {result.get('state')}")
        print(f"   Active: {result.get('active')}")
        print(f"   Cycle ID: {result.get('cycle_id')}")
        print(f"   Base Volume: {result.get('base_volume')}")
        print(f"   Start Price: {result.get('start_price')}")
    else:
        print(f"   ❌ Результат None!")
else:
    print("❌ AUTO_TRADER не найден!")

print("\n" + "="*70)
