import sys
import os

# Ensure repo root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from trade_logger import get_trade_logger


def test_log_sell_shows_green_for_positive_profit(capsys):
    logger = get_trade_logger()
    cur = 'COLORP'
    logger.clear_logs(cur)

    # Positive pnl
    logger.log_sell(cur, 1.0, 100.0, 0.0, 5.0)

    captured = capsys.readouterr()
    out = captured.out

    # Look for ANSI green code around the profit value 5.0000
    assert '\x1b[32m5.0000\x1b[0m' in out, f"Expected green colored profit in output, got: {out!r}"


def test_log_sell_shows_red_for_negative_profit(capsys):
    logger = get_trade_logger()
    cur = 'COLORN'
    logger.clear_logs(cur)

    # Negative pnl
    logger.log_sell(cur, 1.0, 100.0, 0.0, -3.25)

    captured = capsys.readouterr()
    out = captured.out

    # Look for ANSI red code around the profit value -3.2500
    assert '\x1b[31m-3.2500\x1b[0m' in out, f"Expected red colored profit in output, got: {out!r}"
