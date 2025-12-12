import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from autotrader import AutoTrader
from state_manager import get_state_manager


class DummyWS:
    def __init__(self, asks=None):
        self._asks = asks or [['11.867', '2.0']]

    def get_data(self, pair):
        last = self._asks[0][0] if self._asks else '0'
        return {'ticker': {'last': last}, 'orderbook': {'asks': self._asks, 'bids': []}}

    def create_connection(self, pair):
        return None


def test_link_should_rebuy_when_price_drops_below_next_buy():
    sm = get_state_manager()
    sm.set_trading_permission('LINK', True)
    sm.set_auto_trade_enabled(True)

    ws = DummyWS(asks=[['11.867', '2.0']])
    at = AutoTrader(lambda: None, ws, sm)

    last_buy = 11.975
    current_price = 11.867
    base_volume = 0.8
    total_invested = last_buy * base_volume

    # next step requires small drop -> price 11.8875825 (drop ~0.73%), current price 11.867 is below that
    table = [
        {'step': 0, 'rate': last_buy, 'breakeven_price': last_buy, 'target_delta_pct': 0.567},
        {'step': 1, 'rate': last_buy * 0.99, 'decrease_step_pct': 0.733, 'purchase_usd': 10.0, 'cumulative_decrease_pct': -0.733}
    ]

    at._ensure_cycle_struct('LINK')
    at.cycles['LINK'] = {
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

    at._try_rebuy('LINK', 'USDT', current_price)

    assert len(calls) == 1, 'Rebuy should trigger for LINK when current_price < next buy level and asks have volume'
