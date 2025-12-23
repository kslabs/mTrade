import sys
sys.path.append('..')
from trade_logger import get_trade_logger


def test_formatted_logs_no_usdt_or_totalinvest():
    logger = get_trade_logger()
    # Ensure we have formatted logs for a currency - use existing logger state
    # Request a small sample (may be empty, but then the assertions are vacuous)
    formatted = logger.get_formatted_logs(limit=20, currency=list(logger.get_currencies_with_logs())[0] if logger.get_currencies_with_logs() else 'BTC')
    assert all('USDT:' not in s for s in formatted), "Formatted logs must not contain literal 'USDT:'"
    assert all('ВсегоИнвест' not in s for s in formatted), "Formatted logs must not contain 'ВсегоИнвест'"
    # Новое требование: 'СуммПрофит' убран и заменён на 'Профит'. Также убираем 'ОстИнвест'
    assert all('СуммПрофит' not in s for s in formatted), "Formatted logs must not contain 'СуммПрофит'"
    assert all('ОстИнвест' not in s for s in formatted), "Formatted logs must not contain 'ОстИнвест'"

    # Если среди форматированных строк есть продажи, то в продажах должно присутствовать 'Профит:'
    sell_lines = [s for s in formatted if 'Sell{' in s]
    if sell_lines:
        assert all('Профит:' in s for s in sell_lines), "Sell lines should contain 'Профит:'"
