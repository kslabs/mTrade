import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from autotrader import AutoTrader
from state_manager import get_state_manager
import json

sm = get_state_manager()
print('Stored breakeven params for XRP:')
print(json.dumps(sm.get_breakeven_params('XRP'), indent=2))

# Simulate the case
current_price = 1.941
breakeven = 1.922
start_price = 1.922
base = 'XRP'

# compute target_pct to match sell_level provided
sell_level = 1.9329554
target_pct = (sell_level / breakeven - 1.0) * 100.0
print('\nSim params: current_price=', current_price, 'P0=', start_price, 'sell_level=', sell_level, 'target_pct=', target_pct)

class DummyWS:
    def __init__(self, bids=None, asks=None):
        self._bids = bids or [['1.941', '0.3'], ['1.933', '1.0'], ['1.930','2.0']]
        self._asks = asks or [['1.922', '1.0']]
    def get_data(self, pair):
        last = self._bids[0][0] if self._bids else '0'
        return {'ticker': {'last': last}, 'orderbook': {'asks': self._asks, 'bids': self._bids}}
    def create_connection(self, pair):
        return None

ws = DummyWS()
at = AutoTrader(lambda: None, ws, sm)

at._ensure_cycle_struct(base)
at.cycles[base] = {
    'active': True,
    'active_step': 0,
    'table': [{'step':0, 'rate': start_price, 'breakeven_price': breakeven, 'target_delta_pct': target_pct}],
    'last_buy_price': start_price,
    'start_price': start_price,
    'total_invested_usd': 1.922,
    'base_volume': 1.0
}

at._place_limit_order_all_or_nothing = lambda *args, **kwargs: {'success': True, 'filled': args[3]}
print('\nRunning _try_sell:')
at._try_sell(base, 'USDT', current_price)
