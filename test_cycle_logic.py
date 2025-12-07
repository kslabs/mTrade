"""
Тест логики циклов - проверка, что каждая стартовая покупка создаёт новый цикл
"""

from autotrader_v2 import TradingCycle, CycleState

def test_cycle_activation():
    """Тест: каждая активация должна создавать новый цикл с новым ID"""
    
    print("=" * 60)
    print("ТЕСТ: Логика создания новых циклов")
    print("=" * 60)
    
    # Создаём цикл
    cycle = TradingCycle()
    
    print(f"\n1. Начальное состояние:")
    print(f"   cycle_id: {cycle.cycle_id}")
    print(f"   total_cycles_count: {cycle.total_cycles_count}")
    print(f"   state: {cycle.state.value}")
    print(f"   is_active: {cycle.is_active()}")
    
    # Первая стартовая покупка
    print(f"\n2. Первая стартовая покупка (activate):")
    cycle.activate(start_price=100.0, base_volume=1.0, invested_usd=100.0)
    print(f"   cycle_id: {cycle.cycle_id}")
    print(f"   total_cycles_count: {cycle.total_cycles_count}")
    print(f"   state: {cycle.state.value}")
    print(f"   is_active: {cycle.is_active()}")
    
    # Сброс цикла (имитация продажи)
    print(f"\n3. Продажа → сброс цикла (reset):")
    cycle.reset()
    print(f"   cycle_id: {cycle.cycle_id}")
    print(f"   total_cycles_count: {cycle.total_cycles_count}")
    print(f"   state: {cycle.state.value}")
    print(f"   is_active: {cycle.is_active()}")
    
    # Вторая стартовая покупка (НОВЫЙ ЦИКЛ!)
    print(f"\n4. Вторая стартовая покупка (activate) - НОВЫЙ ЦИКЛ:")
    cycle.activate(start_price=105.0, base_volume=1.1, invested_usd=115.5)
    print(f"   cycle_id: {cycle.cycle_id}")
    print(f"   total_cycles_count: {cycle.total_cycles_count}")
    print(f"   state: {cycle.state.value}")
    print(f"   is_active: {cycle.is_active()}")
    
    # Сброс цикла (имитация второй продажи)
    print(f"\n5. Вторая продажа → сброс цикла (reset):")
    cycle.reset()
    print(f"   cycle_id: {cycle.cycle_id}")
    print(f"   total_cycles_count: {cycle.total_cycles_count}")
    print(f"   state: {cycle.state.value}")
    print(f"   is_active: {cycle.is_active()}")
    
    # Третья стартовая покупка
    print(f"\n6. Третья стартовая покупка (activate) - НОВЫЙ ЦИКЛ:")
    cycle.activate(start_price=110.0, base_volume=1.2, invested_usd=132.0)
    print(f"   cycle_id: {cycle.cycle_id}")
    print(f"   total_cycles_count: {cycle.total_cycles_count}")
    print(f"   state: {cycle.state.value}")
    print(f"   is_active: {cycle.is_active()}")
    
    print("\n" + "=" * 60)
    print("✅ ПРОВЕРКА:")
    print(f"   - Всего завершено циклов: {cycle.total_cycles_count}")
    print(f"   - Текущий активный цикл: #{cycle.cycle_id}")
    print("=" * 60)
    
    # Проверяем корректность
    assert cycle.cycle_id == 3, f"Ожидался cycle_id=3, получено {cycle.cycle_id}"
    assert cycle.total_cycles_count == 2, f"Ожидался total_cycles_count=2, получено {cycle.total_cycles_count}"
    assert cycle.is_active(), "Цикл должен быть активным"
    
    print("\n✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    print("   Каждая стартовая покупка создаёт новый цикл с новым ID!")

if __name__ == "__main__":
    test_cycle_activation()
