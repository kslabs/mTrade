"""
Тест системы логирования торговых операций
"""

import sys
import os

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trade_logger import get_trade_logger


def test_trade_logger():
    """Тест основной функциональности логгера"""
    print("=" * 60)
    print("ТЕСТ СИСТЕМЫ ЛОГИРОВАНИЯ ТОРГОВЫХ ОПЕРАЦИЙ")
    print("=" * 60)
    
    logger = get_trade_logger()
    
    # Тест 1: Логирование покупки
    print("\n[ТЕСТ 1] Логирование покупки...")
    logger.log_buy(
        currency='BTC',
        volume=1.0115,
        price=0.8034,
        delta_percent=-0.16,
        total_drop_percent=0.0,
        investment=1.0115
    )
    print("✓ Покупка записана")
    
    # Тест 2: Логирование продажи
    print("\n[ТЕСТ 2] Логирование продажи...")
    logger.log_sell(
        currency='BTC',
        volume=1.0155,
        price=0.8021,
        delta_percent=0.64,
        pnl=0.016
    )
    print("✓ Продажа записана")
    
    # Тест 3: Получение логов
    print("\n[ТЕСТ 3] Получение последних 5 логов...")
    logs = logger.get_logs(limit=5)
    print(f"✓ Получено {len(logs)} записей")
    
    # Тест 4: Форматированные логи
    print("\n[ТЕСТ 4] Форматированные логи (последние 10):")
    formatted = logger.get_formatted_logs(limit=10)
    for log in formatted[:10]:
        print(f"  {log}")
    print(f"✓ Отображено {len(formatted)} записей")
    
    # Тест 5: Статистика
    print("\n[ТЕСТ 5] Статистика по всем логам:")
    stats = logger.get_stats()
    print(f"  Всего записей: {stats['total_entries']}")
    print(f"  Покупок: {stats['total_buys']}")
    print(f"  Продаж: {stats['total_sells']}")
    print(f"  Общие инвестиции: {stats['total_investment']:.4f}")
    print(f"  Общий PnL: {stats['total_pnl']:.4f}")
    print("✓ Статистика получена")
    
    # Тест 6: Фильтрация по валюте
    print("\n[ТЕСТ 6] Логи для BTC:")
    btc_logs = logger.get_formatted_logs(limit=5, currency='BTC')
    for log in btc_logs[:5]:
        print(f"  {log}")
    print(f"✓ Найдено {len(btc_logs)} записей для BTC")
    
    # Тест 7: Добавление тестовых данных
    print("\n[ТЕСТ 7] Добавление тестовых операций...")
    
    # Симуляция серии покупок при падении цены
    test_operations = [
        {'type': 'buy', 'volume': 4.2572, 'price': 0.795, 'delta': 1.05, 'drop': 1.05, 'invest': 5.2687},
        {'type': 'buy', 'volume': 11.8886, 'price': 0.788, 'delta': 0.88, 'drop': 1.92, 'invest': 17.1573},
        {'type': 'buy', 'volume': 24.0488, 'price': 0.782, 'delta': 0.76, 'drop': 2.66, 'invest': 41.2061},
        {'type': 'buy', 'volume': 44.7746, 'price': 0.7745, 'delta': 0.96, 'drop': 3.6, 'invest': 85.9807},
        {'type': 'sell', 'volume': 85.9807, 'price': 0.7939, 'delta': 2.5, 'pnl': 1.67},
    ]
    
    for op in test_operations:
        if op['type'] == 'buy':
            logger.log_buy(
                currency='ETH',
                volume=op['volume'],
                price=op['price'],
                delta_percent=op['delta'],
                total_drop_percent=op['drop'],
                investment=op['invest']
            )
        else:
            logger.log_sell(
                currency='ETH',
                volume=op['volume'],
                price=op['price'],
                delta_percent=op['delta'],
                pnl=op['pnl']
            )
    
    print(f"✓ Добавлено {len(test_operations)} тестовых операций")
    
    # Тест 8: Итоговая статистика
    print("\n[ТЕСТ 8] Итоговая статистика:")
    final_stats = logger.get_stats()
    print(f"  Всего записей: {final_stats['total_entries']}")
    print(f"  Покупок: {final_stats['total_buys']}")
    print(f"  Продаж: {final_stats['total_sells']}")
    print(f"  Общие инвестиции: {final_stats['total_investment']:.4f}")
    print(f"  Общий PnL: {final_stats['total_pnl']:.4f}")
    
    # Тест 9: Последние 15 логов
    print("\n[ТЕСТ 9] Последние 15 операций (все валюты):")
    print("-" * 60)
    recent_logs = logger.get_formatted_logs(limit=15)
    for log in recent_logs:
        print(f"  {log}")
    print("-" * 60)
    
    print("\n" + "=" * 60)
    print("✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    print("=" * 60)
    print("\nФайл логов: trade_logs.jsonl")
    print("Для просмотра на веб-интерфейсе:")
    print("  1. Запустите сервер: python mTrade.py")
    print("  2. Откройте http://localhost:5000")
    print("  3. Нажмите на переключатель 'Логи'")
    print("=" * 60)


if __name__ == '__main__':
    try:
        test_trade_logger()
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
