import sys
import os
import time
import json
import types

# Make sure project root is importable (same trick used in other tests)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from handlers.indicators import get_trade_indicators_impl
from handlers.websocket import ws_get_data as real_ws_get_data
import handlers.indicators as indicators_mod


class DummyAT:
    def __init__(self, last_diagnostics):
        self.last_diagnostics = last_diagnostics


def _fake_ws(price):
    def inner(pair):
        return {'ticker': {'last': str(price)}, 'orderbook': {'asks': [], 'bids': []}}
    return inner


def test_sell_detected_filtered_when_price_below(monkeypatch):
    # Prepare fake AUTO_TRADER with a sell_detected at sell_level=100
    last_diag = {
        'FOO': {
            'last_detected': {
                'sell': {'decision': 'sell_detected', 'timestamp': time.time(), 'reason': 'price_reached_sell_level', 'sell_level': 100}
            },
            'last_decision': None
        }
    }

    dummy = DummyAT(last_diag)

    # Monkeypatch mTrade.AUTO_TRADER to our dummy
    import mTrade
    monkeypatch.setattr(mTrade, 'AUTO_TRADER', dummy)

    # monkeypatch websocket to return price lower than sell_level
    monkeypatch.setattr(indicators_mod, 'ws_get_data', _fake_ws(90))

    # Build a request context and call handler
    from flask import Flask
    app = Flask(__name__)
    with app.test_request_context('/?base_currency=FOO&quote_currency=USDT'):
        resp = get_trade_indicators_impl()
        data = json.loads(resp.get_data(as_text=True))
        ald = data['autotrade_levels']
        # last_detected sell should be filtered away because current price < sell_level
        assert ald.get('last_detected') is None or 'sell' not in (ald.get('last_detected') or {} )


def test_sell_detected_kept_when_price_at_or_above(monkeypatch):
    last_diag = {
        'FOO': {
            'last_detected': {
                'sell': {'decision': 'sell_detected', 'timestamp': time.time(), 'reason': 'price_reached_sell_level', 'sell_level': 100}
            },
            'last_decision': None
        }
    }

    dummy = DummyAT(last_diag)
    import mTrade
    monkeypatch.setattr(mTrade, 'AUTO_TRADER', dummy)
    monkeypatch.setattr(indicators_mod, 'ws_get_data', _fake_ws(100.5))

    from flask import Flask
    app = Flask(__name__)
    with app.test_request_context('/?base_currency=FOO&quote_currency=USDT'):
        resp = get_trade_indicators_impl()
        data = json.loads(resp.get_data(as_text=True))
        ald = data['autotrade_levels']
        # last_detected sell should remain present
        assert ald.get('last_detected') and 'sell' in ald.get('last_detected')


def test_diagnostic_decision_cleared_when_price_below_sell_price(monkeypatch):
    # last_decision is 'sell' but current price below computed sell_price -> diagnostic_decision should be cleared
    last_diag = {
        'FOO': {
            'last_detected': {},
            'last_decision': {'decision': 'sell', 'timestamp': time.time(), 'reason': 'placed_sell'}
        }
    }

    dummy = DummyAT(last_diag)
    import mTrade
    monkeypatch.setattr(mTrade, 'AUTO_TRADER', dummy)

    # provide a table through cycles so handler computes sell_price = 100 * (1 + 1%) = 101
    dummy.cycles = {'FOO': {'active': False, 'active_step': 0, 'table': [{'step': 0, 'rate': 100, 'breakeven_price': 100, 'target_delta_pct': 1.0}], 'last_buy_price': 100, 'start_price': 100, 'total_invested_usd': 100, 'base_volume': 1.0}}

    # price below sell_price
    monkeypatch.setattr(indicators_mod, 'ws_get_data', _fake_ws(99.0))

    from flask import Flask
    app = Flask(__name__)
    with app.test_request_context('/?base_currency=FOO&quote_currency=USDT'):
        resp = get_trade_indicators_impl()
        data = json.loads(resp.get_data(as_text=True))
        ald = data['autotrade_levels']
        # diagnostic decision must be cleared because price < sell_price
        assert ald.get('diagnostic_decision') is None


def test_diagnostic_decision_kept_when_price_at_or_above_sell_price(monkeypatch):
    # last_decision is 'sell' and current price >= sell_price -> should be kept
    last_diag = {
        'FOO': {
            'last_detected': {},
            'last_decision': {'decision': 'sell', 'timestamp': time.time(), 'reason': 'placed_sell'}
        }
    }

    dummy = DummyAT(last_diag)
    import mTrade
    monkeypatch.setattr(mTrade, 'AUTO_TRADER', dummy)

    dummy.cycles = {'FOO': {'active': False, 'active_step': 0, 'table': [{'step': 0, 'rate': 100, 'breakeven_price': 100, 'target_delta_pct': 1.0}], 'last_buy_price': 100, 'start_price': 100, 'total_invested_usd': 100, 'base_volume': 1.0}}

    # price at or above sell_price
    monkeypatch.setattr(indicators_mod, 'ws_get_data', _fake_ws(101.5))

    from flask import Flask
    app = Flask(__name__)
    with app.test_request_context('/?base_currency=FOO&quote_currency=USDT'):
        resp = get_trade_indicators_impl()
        data = json.loads(resp.get_data(as_text=True))
        ald = data['autotrade_levels']
        assert ald.get('diagnostic_decision') is not None and ald['diagnostic_decision']['decision'] == 'sell'
