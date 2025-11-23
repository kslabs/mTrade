import sys
import json
sys.path.append('..')

from flask import Flask

import handlers.quick_trades as qt


class DummyAPI:
    def __init__(self):
        self.orders = []
    def get_account_balance(self):
        return [{'currency': 'USDT', 'available': '1000'}]
    def get_currency_pair_details_exact(self, pair):
        # return amount_precision=4 and min_quote_amount=3
        return {'id': pair, 'min_quote_amount': '3', 'min_base_amount': '0.001', 'amount_precision': 4, 'precision': 8}
    def create_spot_order(self, **kwargs):
        # pretend order created
        return {'id': 'ok'}


def fake_ws_get_data(pair):
    # orderbook with best ask that causes rounding down to 0.0011 typical issue
    return {'orderbook': {'asks': [[2721.01, '10'], [2722.0, '5']], 'bids': [[2721.0, '10']]}, 'ticker': {'last': '2721.5'}}


def test_quick_buy_min_uses_ceil(monkeypatch):
    # monkeypatch API client and websocket
    monkeypatch.setattr('handlers.quick_trades.Config.load_secrets_by_mode', lambda mode: ('k','s'))
    monkeypatch.setattr('handlers.quick_trades.Config.load_network_mode', lambda: 'test')
    monkeypatch.setattr('handlers.quick_trades.GateAPIClient', lambda k,s,n: DummyAPI())
    monkeypatch.setattr('handlers.quick_trades.ws_get_data', lambda p: fake_ws_get_data(p))

    app = Flask(__name__)
    with app.test_request_context(json={'base_currency': 'ETH', 'quote_currency': 'USDT'}):
        resp = qt.quick_buy_min_impl()
        data = resp.get_json()
        assert data['success'] is True
        # amount should be rounded up to precision 4 -> 0.0012
        assert data['amount'] >= 0.0012
