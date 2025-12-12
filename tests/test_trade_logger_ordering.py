import sys
import os

# Ensure repo root is on sys.path so test can import project modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from trade_logger import get_trade_logger


def test_get_formatted_logs_newest_first():
    logger = get_trade_logger()
    currency = 'TESTORD'

    # Очистим предыдущие логи (если были)
    logger.clear_logs(currency)

    # Создадим две записи: сначала Buy, затем Sell
    logger.log_buy(currency, 1.0, 100.0, 0.0, 0.0, 100.0)
    logger.log_sell(currency, 1.0, 110.0, 0.0, 10.0)

    # Получаем форматированные записи — ожидаем, что новейшая (Sell) появится первой
    formatted = logger.get_formatted_logs(limit=10, currency=currency)

    assert len(formatted) >= 2, "Должно быть по крайней мере 2 записи"
    # Первая строка должна быть продажей (Sell{), а последняя — покупкой
    assert 'Sell{' in formatted[0], f"Ожидается, что первая строка — Sell (получено: {formatted[0]})"
    assert 'Buy{' in formatted[-1], f"Ожидается, что последняя строка — Buy (получено: {formatted[-1]})"
