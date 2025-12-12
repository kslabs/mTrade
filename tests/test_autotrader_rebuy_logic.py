import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from autotrader import AutoTrader
from state_manager import get_state_manager


class DummyWS:
    def __init__(self, asks=None):
        self._asks = asks or [['127.00', '10']]

    def get_data(self, pair):
        last = self._asks[0][0] if self._asks else '0'
        return {'ticker': {'last': last}, 'orderbook': {'asks': self._asks, 'bids': []}}

    def create_connection(self, pair):
        return None


def setup_cycle_rebuy(at: AutoTrader, base: str, last_buy: float, base_volume: float, table=None):
    at._ensure_cycle_struct(base)
    if table is None:
        # default table: two steps so next_step exists
        table = [
            {'step': 0, 'rate': last_buy, 'breakeven_price': last_buy, 'target_delta_pct': 0.5},
            {'step': 1, 'rate': last_buy * 0.98, 'decrease_step_pct': 0.1, 'purchase_usd': 10.0, 'cumulative_decrease_pct': 0.1}
        ]
    at.cycles[base] = {
        'active': True,
        'active_step': 0,
        'table': table,
        'last_buy_price': last_buy,
        'start_price': last_buy,
        'total_invested_usd': last_buy * base_volume,
        'base_volume': base_volume
    }


def test_rebuy_triggers_on_small_drop_when_liquidity():
    sm = get_state_manager()
    sm.set_trading_permission('RB1', True)
    sm.set_auto_trade_enabled(True)

    # last_buy 127.22 -> next_step requires 0.1% drop -> current price 127.05 (0.133% drop) should trigger
    asks = [['127.05', '1.0']]
    ws = DummyWS(asks=asks)
    at = AutoTrader(lambda: None, ws, sm)

    setup_cycle_rebuy(at, 'RB1', 127.22, 0.08)

    calls = []

    def fake_place(*args, **kwargs):
        calls.append((args, kwargs))
        return {'success': True, 'filled': args[3]}

    at._place_limit_order_all_or_nothing = fake_place

    at._try_rebuy('RB1', 'USDT', 127.05)

    assert len(calls) == 1, "Rebuy should trigger and place order when drop >= decrease_step_pct and liquidity available"


def test_rebuy_does_not_trigger_if_drop_not_enough():
    sm = get_state_manager()
    sm.set_trading_permission('RB2', True)
    sm.set_auto_trade_enabled(True)

    asks = [['127.15', '10']]
    ws = DummyWS(asks=asks)
    at = AutoTrader(lambda: None, ws, sm)

    setup_cycle_rebuy(at, 'RB2', 127.22, 0.08)

    calls = []

    def fake_place(*args, **kwargs):
        calls.append((args, kwargs))
        return {'success': True, 'filled': args[3]}

    at._place_limit_order_all_or_nothing = fake_place

    # current price 127.15 => drop_pct ~0.054% < 0.1% -> should NOT trigger
    at._try_rebuy('RB2', 'USDT', 127.15)

    assert len(calls) == 0, "Rebuy should not trigger when price drop less than decrease_step_pct"
