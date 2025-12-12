#!/usr/bin/env python3
"""Тест расчета профита: проверка, что профит сбрасывается при новом цикле"""

from trade_logger import get_trade_logger
import time

logger = get_trade_logger()

print("=" * 80)
print("ТЕСТ: Проверка расчета профита")
print("=" * 80)
print()

# Цикл 1
print("🔵 ЦИКЛ #1")
print("-" * 80)

# Покупка #1 (стартовая)
print("1. Покупка стартовая (delta=0, drop=0) → должен сброситься профит")
logger.log_buy(
    currency="TEST",
    volume=0.003,
    price=3387.77,
    delta_percent=0.0,  # Стартовая покупка
    total_drop_percent=0.0,
    investment=10.0
)
print()

# Продажа #1
print("2. Продажа #1: PnL=0.05")
logger.log_sell(
    currency="TEST",
    volume=0.003,
    price=3405.0,
    delta_percent=0.5,
    pnl=0.05,
    source="AUTO"
)
print(f"   Ожидается: Профит=0.05")
print(f"   Реально: Профит={logger.total_pnl.get('TEST', 0):.4f}")
print()

# Цикл 2
print("🔵 ЦИКЛ #2")
print("-" * 80)

# Покупка #2 (стартовая)
print("3. Покупка стартовая (delta=0, drop=0) → должен сброситься профит")
logger.log_buy(
    currency="TEST",
    volume=0.003,
    price=3400.0,
    delta_percent=0.0,  # Стартовая покупка
    total_drop_percent=0.0,
    investment=10.0
)
print()

# Продажа #2
print("4. Продажа #2: PnL=0.06")
logger.log_sell(
    currency="TEST",
    volume=0.003,
    price=3420.0,
    delta_percent=0.6,
    pnl=0.06,
    source="AUTO"
)
print(f"   Ожидается: Профит=0.06 (сброшен при новой покупке)")
print(f"   Реально: Профит={logger.total_pnl.get('TEST', 0):.4f}")
print()

# Цикл 3
print("🔵 ЦИКЛ #3")
print("-" * 80)

# Покупка #3 (стартовая)
print("5. Покупка стартовая (delta=0, drop=0) → должен сброситься профит")
logger.log_buy(
    currency="TEST",
    volume=0.003,
    price=3410.0,
    delta_percent=0.0,  # Стартовая покупка
    total_drop_percent=0.0,
    investment=10.0
)
print()

# Продажа #3
print("6. Продажа #3: PnL=0.07")
logger.log_sell(
    currency="TEST",
    volume=0.003,
    price=3435.0,
    delta_percent=0.7,
    pnl=0.07,
    source="AUTO"
)
print(f"   Ожидается: Профит=0.07 (сброшен при новой покупке)")
print(f"   Реально: Профит={logger.total_pnl.get('TEST', 0):.4f}")
print()

# Проверка результата
print("=" * 80)
print("РЕЗУЛЬТАТ ТЕСТА")
print("=" * 80)
expected_pnl = 0.07
actual_pnl = logger.total_pnl.get('TEST', 0)

if abs(actual_pnl - expected_pnl) < 0.0001:
    print(f"✅ ТЕСТ ПРОЙДЕН: Профит={actual_pnl:.4f} (ожидалось {expected_pnl:.4f})")
    print("✅ Профит корректно сбрасывается при начале нового цикла")
else:
    print(f"❌ ТЕСТ НЕ ПРОЙДЕН: Профит={actual_pnl:.4f} (ожидалось {expected_pnl:.4f})")
    print("❌ Профит накапливается неправильно")

print("=" * 80)
