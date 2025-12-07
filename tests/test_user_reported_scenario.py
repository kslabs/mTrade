import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from autotrader import AutoTrader
from state_manager import get_state_manager

class DummyWS:
    def __init__(self, bids=None, asks=None):
        self._bids = bids or [['1.936', '1.0']]
        self._asks = asks or [['1.922', '1.0']]

    def get_data(self, pair):
        last = self._bids[0][0] if self._bids else (self._asks[0][0] if self._asks else '0')
        return {'ticker': {'last': last}, 'orderbook': {'asks': self._asks, 'bids': self._bids}}

    def create_connection(self, pair):
        return None


def setup_cycle(at: AutoTrader, base: str, start_price: float, total_invested_usd: float, base_volume: float, breakeven: float, target_delta_pct: float):
    at._ensure_cycle_struct(base)
    at.cycles[base] = {
        'active': True,
        'active_step': 0,
        'table': [{'step': 0, 'rate': start_price, 'breakeven_price': breakeven, 'target_delta_pct': target_delta_pct}],
        'last_buy_price': start_price,
        'start_price': start_price,
        'total_invested_usd': total_invested_usd,
        'base_volume': base_volume
    }


def test_user_reported_sell_case():
    sm = get_state_manager()
    sm.set_trading_permission('USR', True)
    sm.set_auto_trade_enabled(True)

    # Using the numbers from your message
    current_price = 1.936
    sell_level = 1.9329554
    breakeven = 1.922
    start_price = 1.922
    total_invested = 1.9079694
    base_volume = 1.0

    # Provide bids that should be enough
    bids = [['1.936', '0.5'], ['1.933', '1.0']]
    ws = DummyWS(bids=bids, asks=[['1.922', '1.0']])
    at = AutoTrader(lambda: None, ws, sm)

    # set exact target to reproduce sell_level 1.9329554
    target_pct = (1.9329554 / breakeven - 1.0) * 100.0
    setup_cycle(at, 'USR', start_price, total_invested, base_volume, breakeven, target_pct)

    calls = []
    def fake_place(*args, **kwargs):
        calls.append((args, kwargs))
        return {'success': True, 'filled': args[3]}
    at._place_limit_order_all_or_nothing = fake_place

    # call sell — expected to attempt sell
    at._try_sell('USR', 'USDT', current_price)

    assert len(calls) > 0, 'Expected sell attempt in the reported scenario'


def test_user_reported_rebuy_case():
    sm = get_state_manager()
    sm.set_trading_permission('RUS', True)
    sm.set_auto_trade_enabled(True)

    # scenario: last_buy=127.22, current_price=127.05 -> should trigger rebuy if decrease step small
    last_buy = 127.22
    current_price = 127.05
    base_volume = 0.08
    total_invested = last_buy * base_volume

    asks = [['127.05', '1.0']]
    ws = DummyWS(bids=[], asks=asks)
    at = AutoTrader(lambda: None, ws, sm)

    # Table: create a next step with decrease_step_pct small so 127.05 triggers it
    table = [
        {'step':0, 'rate': last_buy, 'breakeven_price': last_buy, 'target_delta_pct':0.5},
        {'step':1, 'rate': last_buy*0.98, 'decrease_step_pct':0.1, 'purchase_usd': 10.0, 'cumulative_decrease_pct': -0.1}
    ]

    at._ensure_cycle_struct('RUS')
    at.cycles['RUS'] = {
        'active': True,
        'active_step': 0,
        'table': table,
        'last_buy_price': last_buy,
        'start_price': last_buy,
        'total_invested_usd': total_invested,
        'base_volume': base_volume
    }

    calls = []
    def fake_place(*args, **kwargs):
        calls.append((args, kwargs))
        return {'success': True, 'filled': args[3]}
    at._place_limit_order_all_or_nothing = fake_place

    at._try_rebuy('RUS', 'USDT', current_price)
    assert len(calls) == 1, 'Expected rebuy attempt for reported scenario'
