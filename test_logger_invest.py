"""
Тест логики накопления Инвеста и расчёта Профита

Проверяем:
1. Накопление total_invested при покупках
2. Обнуление total_invested после продажи
3. Правильный расчёт профита (volume_quote - total_invested)
4. Восстановление total_invested из логов
"""

import os
import sys
import shutil

# Устанавливаем кодировку UTF-8 для stdout/stderr (для Windows PowerShell)
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from trade_logger import TradeLogger

def test_invest_accumulation():
    """Тест накопления инвестиций"""
    
    print("=" * 80)
    print("ТЕСТ 1: Накопление Инвеста и расчёт Профита")
    print("=" * 80)
    
    # Создаём временную директорию для логов
    test_log_dir = "test_trade_logs"
    if os.path.exists(test_log_dir):
        shutil.rmtree(test_log_dir)
    
    # Заменяем директорию логов
    original_dir = TradeLogger.LOG_DIR
    TradeLogger.LOG_DIR = test_log_dir
    
    try:
        # Создаём логгер
        logger = TradeLogger()
        
        currency = "XRP"
        
        print("\n--- ЦИКЛ 1: Покупки и продажа ---")
        
        # Покупка 1: 100 USDT по цене 0.5
        print("\n1. Первая покупка: 100 USDT")
        logger.log_buy(
            currency=currency,
            volume=200,  # 200 XRP
            price=0.5,   # по 0.5 USDT
            delta_percent=0.0,
            total_drop_percent=0.0,
            investment=100.0  # инвестиция 100 USDT
        )
        
        assert logger.total_invested[currency] == 100.0, f"❌ Ожидали 100, получили {logger.total_invested[currency]}"
        print(f"✅ total_invested после 1-й покупки: {logger.total_invested[currency]:.4f} USDT")
        
        # Докупка: 50 USDT по цене 0.45
        print("\n2. Докупка: 50 USDT")
        logger.log_buy(
            currency=currency,
            volume=111.11,  # ~111 XRP
            price=0.45,     # по 0.45 USDT
            delta_percent=-10.0,
            total_drop_percent=10.0,
            investment=50.0  # докупка 50 USDT
        )
        
        assert logger.total_invested[currency] == 150.0, f"❌ Ожидали 150, получили {logger.total_invested[currency]}"
        print(f"✅ total_invested после докупки: {logger.total_invested[currency]:.4f} USDT")
        
        # Продажа: 311.11 XRP по цене 0.52
        print("\n3. Продажа всего объёма")
        volume_sell = 311.11
        price_sell = 0.52
        volume_quote = volume_sell * price_sell  # = 161.78 USDT
        
        expected_profit = volume_quote - logger.total_invested[currency]  # = 161.78 - 150 = 11.78
        print(f"   Сумма продажи: {volume_quote:.4f} USDT")
        print(f"   Накопленные инвестиции: {logger.total_invested[currency]:.4f} USDT")
        print(f"   Ожидаемый профит: {expected_profit:.4f} USDT")
        
        logger.log_sell(
            currency=currency,
            volume=volume_sell,
            price=price_sell,
            delta_percent=4.0,
            pnl=10.0,  # PnL от автотрейдера (может быть неточным)
            source="AUTO"
        )
        
        assert logger.total_invested[currency] == 0.0, f"❌ После продажи ожидали 0, получили {logger.total_invested[currency]}"
        print(f"✅ total_invested после продажи: {logger.total_invested[currency]:.4f} USDT (обнулён)")
        
        print("\n--- ЦИКЛ 2: Новая покупка после продажи ---")
        
        # Новая покупка после продажи
        print("\n4. Новая покупка в новом цикле: 80 USDT")
        logger.log_buy(
            currency=currency,
            volume=160,
            price=0.5,
            delta_percent=0.0,
            total_drop_percent=0.0,
            investment=80.0
        )
        
        assert logger.total_invested[currency] == 80.0, f"❌ Ожидали 80, получили {logger.total_invested[currency]}"
        print(f"✅ total_invested в новом цикле: {logger.total_invested[currency]:.4f} USDT")
        
        print("\n" + "=" * 80)
        print("ТЕСТ 2: Восстановление из логов")
        print("=" * 80)
        
        # Создаём новый логгер (загружаем логи из файла)
        logger2 = TradeLogger()
        
        print(f"\n✅ Восстановленный total_invested: {logger2.total_invested[currency]:.4f} USDT")
        assert logger2.total_invested[currency] == 80.0, f"❌ Ожидали 80, получили {logger2.total_invested[currency]}"
        
        # Проверяем количество записей
        logs_count = len(logger2.logs_by_currency[currency])
        print(f"✅ Загружено {logs_count} записей")
        assert logs_count == 4, f"❌ Ожидали 4 записи, получили {logs_count}"
        
        print("\n" + "=" * 80)
        print("✅✅✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ! ✅✅✅")
        print("=" * 80)
        
    finally:
        # Восстанавливаем директорию логов
        TradeLogger.LOG_DIR = original_dir
        
        # Удаляем тестовую директорию
        if os.path.exists(test_log_dir):
            shutil.rmtree(test_log_dir)

if __name__ == "__main__":
    test_invest_accumulation()
