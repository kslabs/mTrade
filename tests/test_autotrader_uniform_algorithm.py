import sys
import os

# Make sure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from autotrader import AutoTrader
from state_manager import get_state_manager


class DummyWS:
    def __init__(self, bids=None):
        self._bids = bids or [['100.00', '1']]

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


def test_same_sell_decision_for_two_bases():
    sm = get_state_manager()
    sm.set_trading_permission('A1', True)
    sm.set_trading_permission('B1', True)
    sm.set_auto_trade_enabled(True)

    # both bases use same breakeven & params
    params_A = sm.get_breakeven_params('A1')
    params_A['orderbook_level'] = 1
    sm.set_breakeven_params('A1', params_A)
    params_B = sm.get_breakeven_params('B1')
    params_B['orderbook_level'] = 1
    sm.set_breakeven_params('B1', params_B)

    # orderbook with sufficient liquidity for both
    ws = DummyWS(bids=[['101.00', '2.0']])
    at = AutoTrader(lambda: None, ws, sm)

    setup_cycle(at, 'A1', 100.0, 0.5, 1.0)  # sell_level = 100.5
    setup_cycle(at, 'B1', 100.0, 0.5, 1.0)

    calls = {'A1': 0, 'B1': 0}

    def fake_place(*args, **kwargs):
        base = args[1]
        calls[base] += 1
        return {'success': True, 'filled': args[3]}

    at._place_limit_order_all_or_nothing = fake_place

    # Both should attempt sell with same inputs
    at._try_sell('A1', 'USDT', 101.0)
    at._try_sell('B1', 'USDT', 101.0)

    assert calls['A1'] == 1 and calls['B1'] == 1, "Both bases should have attempted to sell with identical conditions"


def test_same_no_sell_when_price_below_target_for_two_bases():
    sm = get_state_manager()
    sm.set_trading_permission('A2', True)
    sm.set_trading_permission('B2', True)
    sm.set_auto_trade_enabled(True)

    ws = DummyWS(bids=[['100.05', '10.0']])
    at = AutoTrader(lambda: None, ws, sm)

    setup_cycle(at, 'A2', 100.0, 0.5, 1.0)  # sell_level = 100.5
    setup_cycle(at, 'B2', 100.0, 0.5, 1.0)

    calls = {'A2': 0, 'B2': 0}

    def fake_place(*args, **kwargs):
        base = args[1]
        calls[base] += 1
        return {'success': True, 'filled': args[3]}

    at._place_limit_order_all_or_nothing = fake_place

    # Price below sell level — neither should sell
    at._try_sell('A2', 'USDT', 100.05)
    at._try_sell('B2', 'USDT', 100.05)

    assert calls['A2'] == 0 and calls['B2'] == 0, "Neither base should place sell when price below target"
