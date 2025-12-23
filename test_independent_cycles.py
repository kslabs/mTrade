"""
Тест: Проверка независимости профитов между циклами

Этот скрипт проверяет, что профиты не накапливаются между циклами.
"""

import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trade_logger import TradeLogger


def test_independent_cycles():
    """Проверка независимости профитов между циклами"""
    
    print("=" * 80)
    print("ТЕСТ: Независимость профитов между циклами")
    print("=" * 80)
    
    # Создаём новый логгер
    logger = TradeLogger()
    
    # Очищаем логи тестовой валюты
    logger.clear_logs(currency="TEST")
    
    # ========== ЦИКЛ 1 ==========
    print("\n🔵 ЦИКЛ 1")
    print("-" * 80)
    
    # Покупка 1
    logger.log_buy(
        currency="TEST",
        volume=10.0,
        price=1.0,
        delta_percent=-2.0,
        total_drop_percent=-2.0,
        investment=10.0
    )
    print(f"   После покупки 1: total_invested = {logger.total_invested.get('TEST', 0):.4f}")
    
    # Покупка 2
    logger.log_buy(
        currency="TEST",
        volume=10.0,
        price=0.95,
        delta_percent=-5.0,
        total_drop_percent=-5.0,
        investment=9.5
    )
    print(f"   После покупки 2: total_invested = {logger.total_invested.get('TEST', 0):.4f}")
    
    # Продажа (профит должен быть +0.5)
    logger.log_sell(
        currency="TEST",
        volume=20.0,
        price=1.0,
        delta_percent=5.26,
        pnl=0.5,
        source="AUTO"
    )
    print(f"   После продажи: total_invested = {logger.total_invested.get('TEST', 0):.4f}")
    
    # Проверяем первый цикл
    stats = logger.get_stats(currency="TEST")
    cycle1_profit = stats['cycle_profits'][0] if stats['cycle_profits'] else 0
    print(f"\n   ✅ Профит цикла 1: {cycle1_profit:.4f} USDT")
    print(f"      Ожидается: 0.5000 USDT (20.0 * 1.0 - 19.5)")
    
    # ========== ЦИКЛ 2 ==========
    print("\n🟢 ЦИКЛ 2")
    print("-" * 80)
    
    # Покупка 1
    logger.log_buy(
        currency="TEST",
        volume=10.0,
        price=1.0,
        delta_percent=-2.0,
        total_drop_percent=-2.0,
        investment=10.0
    )
    print(f"   После покупки 1: total_invested = {logger.total_invested.get('TEST', 0):.4f}")
    
    # Покупка 2
    logger.log_buy(
        currency="TEST",
        volume=10.0,
        price=0.90,
        delta_percent=-10.0,
        total_drop_percent=-10.0,
        investment=9.0
    )
    print(f"   После покупки 2: total_invested = {logger.total_invested.get('TEST', 0):.4f}")
    
    # Продажа (профит должен быть +2.0)
    logger.log_sell(
        currency="TEST",
        volume=20.0,
        price=1.05,
        delta_percent=16.67,
        pnl=2.0,
        source="AUTO"
    )
    print(f"   После продажи: total_invested = {logger.total_invested.get('TEST', 0):.4f}")
    
    # Проверяем второй цикл
    stats = logger.get_stats(currency="TEST")
    cycle2_profit = stats['cycle_profits'][1] if len(stats['cycle_profits']) > 1 else 0
    print(f"\n   ✅ Профит цикла 2: {cycle2_profit:.4f} USDT")
    print(f"      Ожидается: 2.0000 USDT (20.0 * 1.05 - 19.0)")
    
    # ========== ЦИКЛ 3 (УБЫТОЧНЫЙ) ==========
    print("\n🔴 ЦИКЛ 3 (убыточный)")
    print("-" * 80)
    
    # Покупка 1
    logger.log_buy(
        currency="TEST",
        volume=10.0,
        price=1.0,
        delta_percent=-2.0,
        total_drop_percent=-2.0,
        investment=10.0
    )
    print(f"   После покупки 1: total_invested = {logger.total_invested.get('TEST', 0):.4f}")
    
    # Покупка 2
    logger.log_buy(
        currency="TEST",
        volume=10.0,
        price=0.85,
        delta_percent=-15.0,
        total_drop_percent=-15.0,
        investment=8.5
    )
    print(f"   После покупки 2: total_invested = {logger.total_invested.get('TEST', 0):.4f}")
    
    # Продажа (профит должен быть -1.5)
    logger.log_sell(
        currency="TEST",
        volume=20.0,
        price=0.85,
        delta_percent=0.0,
        pnl=-1.5,
        source="AUTO"
    )
    print(f"   После продажи: total_invested = {logger.total_invested.get('TEST', 0):.4f}")
    
    # Проверяем третий цикл
    stats = logger.get_stats(currency="TEST")
    cycle3_profit = stats['cycle_profits'][2] if len(stats['cycle_profits']) > 2 else 0
    print(f"\n   ✅ Профит цикла 3: {cycle3_profit:.4f} USDT")
    print(f"      Ожидается: -1.5000 USDT (20.0 * 0.85 - 18.5)")
    
    # ========== ИТОГОВАЯ ПРОВЕРКА ==========
    print("\n" + "=" * 80)
    print("ИТОГОВАЯ ПРОВЕРКА")
    print("=" * 80)
    
    stats = logger.get_stats(currency="TEST")
    
    print(f"\nСтатистика:")
    print(f"   Всего циклов: {stats['total_cycles']}")
    print(f"   Всего покупок: {stats['total_buys']}")
    print(f"   Всего продаж: {stats['total_sells']}")
    print(f"   Последний профит: {stats['last_cycle_profit']:.4f} USDT")
    print(f"   Средний профит: {stats['avg_cycle_profit']:.4f} USDT")
    
    print(f"\nПрофиты по циклам:")
    for i, profit in enumerate(stats['cycle_profits'], 1):
        color = "🟢" if profit >= 0 else "🔴"
        print(f"   {color} Цикл {i}: {profit:.4f} USDT")
    
    # Проверяем форматированные логи
    print("\n" + "=" * 80)
    print("ФОРМАТИРОВАННЫЕ ЛОГИ (последние 10 записей)")
    print("=" * 80)
    formatted_logs = logger.get_formatted_logs(limit=10, currency="TEST")
    for log in formatted_logs:
        print(log)
    
    # ========== РЕЗУЛЬТАТЫ ==========
    print("\n" + "=" * 80)
    print("РЕЗУЛЬТАТЫ ТЕСТА")
    print("=" * 80)
    
    # Проверки
    checks = []
    
    # Проверка 1: Профит цикла 1
    if abs(cycle1_profit - 0.5) < 0.0001:
        checks.append(("✅", "Профит цикла 1 правильный"))
    else:
        checks.append(("❌", f"Профит цикла 1 неправильный: {cycle1_profit:.4f} != 0.5000"))
    
    # Проверка 2: Профит цикла 2
    if abs(cycle2_profit - 2.0) < 0.0001:
        checks.append(("✅", "Профит цикла 2 правильный"))
    else:
        checks.append(("❌", f"Профит цикла 2 неправильный: {cycle2_profit:.4f} != 2.0000"))
    
    # Проверка 3: Профит цикла 3
    if abs(cycle3_profit - (-1.5)) < 0.0001:
        checks.append(("✅", "Профит цикла 3 правильный"))
    else:
        checks.append(("❌", f"Профит цикла 3 неправильный: {cycle3_profit:.4f} != -1.5000"))
    
    # Проверка 4: Профиты не суммируются (цикл 2 != цикл 1 + прибыль 2)
    if abs(cycle2_profit - 2.0) < 0.0001:  # Не 2.5 (0.5 + 2.0)
        checks.append(("✅", "Профиты НЕ суммируются между циклами"))
    else:
        checks.append(("❌", "Профиты суммируются между циклами!"))
    
    # Проверка 5: Средний профит
    expected_avg = (0.5 + 2.0 - 1.5) / 3
    if abs(stats['avg_cycle_profit'] - expected_avg) < 0.0001:
        checks.append(("✅", f"Средний профит правильный: {stats['avg_cycle_profit']:.4f}"))
    else:
        checks.append(("❌", f"Средний профит неправильный: {stats['avg_cycle_profit']:.4f} != {expected_avg:.4f}"))
    
    # Выводим результаты
    print()
    for check, message in checks:
        print(f"{check} {message}")
    
    # Общий результат
    all_passed = all(check == "✅" for check, _ in checks)
    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Профиты независимы между циклами.")
    else:
        print("⚠️ ТЕСТЫ НЕ ПРОЙДЕНЫ! Требуется дополнительная проверка.")
    print("=" * 80)
    
    # Очищаем тестовые логи
    logger.clear_logs(currency="TEST")
    
    return all_passed


if __name__ == "__main__":
    test_independent_cycles()
