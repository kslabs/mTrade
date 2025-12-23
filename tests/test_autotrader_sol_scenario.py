import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from autotrader import AutoTrader
from state_manager import get_state_manager


class DummyWS:
    def __init__(self, bids=None):
        self._bids = bids or [['126.4', '0.08']]

    def get_data(self, pair):
        last = self._bids[0][0] if self._bids else '0'
        return {'ticker': {'last': last}, 'orderbook': {'asks': [], 'bids': self._bids}}

    def create_connection(self, pair):
        return None


def setup_cycle(at: AutoTrader, base: str, breakeven: float, target_pct: float, base_volume: float):
    at._ensure_cycle_struct(base)
    at.cycles[base] = {
        'active': True,
        'active_step': 0,
        'table': [{'step': 0, 'rate': breakeven, 'breakeven_price': breakeven, 'target_delta_pct': target_pct}],
        'last_buy_price': breakeven,
        'start_price': breakeven,
        'total_invested_usd': breakeven * base_volume,
        'base_volume': base_volume
    }


def test_sol_fractional_level_no_sell_insufficient_depth():
    sm = get_state_manager()
    sm.set_trading_permission('SOL', True)
    sm.set_auto_trade_enabled(True)

    params = sm.get_breakeven_params('SOL')
    # use fractional 0.26 like the reported case
    params['orderbook_level'] = 0.26
    sm.set_breakeven_params('SOL', params)

    # bids length 3 -> level = ceil(3*0.26) = 1 -> level 1 amount 0.05 insufficient
    ws = DummyWS(bids=[['127.0', '0.05'], ['126.8', '0.5'], ['126.6', '1.0']])
    at = AutoTrader(lambda: None, ws, sm)

    setup_cycle(at, 'SOL', 126.4, 0.5, 0.08)  # last_buy 126.4 base_volume 0.08

    calls = []

    def fake_place(*args, **kwargs):
        calls.append((args, kwargs))
        return {'success': True, 'filled': args[3]}

    at._place_limit_order_all_or_nothing = fake_place

    # current price meets sell_level (>=126.4 * 1.005 = 127.032), but level1 amount insufficient, so no sell
    at._try_sell('SOL', 'USDT', 127.05)
    assert calls == [], "No sell expected when the computed level has insufficient liquidity"


def test_sol_fractional_level_sell_when_sufficient():
    sm = get_state_manager()
    sm.set_trading_permission('SOL', True)
    sm.set_auto_trade_enabled(True)

    params = sm.get_breakeven_params('SOL')
    params['orderbook_level'] = 0.26
    sm.set_breakeven_params('SOL', params)

    # bids: level 1 small, level 2 (ceil(4*0.26)=2) has enough
    ws = DummyWS(bids=[['127.0', '0.05'], ['127.0', '1.0'], ['126.6', '1.0'], ['126.4', '2.0']])
    at = AutoTrader(lambda: None, ws, sm)

    setup_cycle(at, 'SOL', 126.4, 0.5, 0.08)

    calls = []

    def fake_place(*args, **kwargs):
        calls.append((args, kwargs))
        return {'success': True, 'filled': args[3]}

    at._place_limit_order_all_or_nothing = fake_place

    # current price above sell_level and the fractional computed level has enough amount -> sell
    at._try_sell('SOL', 'USDT', 127.05)
    assert len(calls) == 1, "Expected sell when fractional orderbook level points to sufficient liquidity"
