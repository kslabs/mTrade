import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from autotrader import AutoTrader
from state_manager import get_state_manager

sm = get_state_manager()
print('breakeven params for SOL:', sm.get_breakeven_params('SOL'))

# Provided scenario
current_price = 127.92
start_price = 126.93
breakeven = 126.93
sell_level = 127.653501
# compute target pct to match the sell_level
target_pct = (sell_level / breakeven - 1.0) * 100.0
print('Sim params --> current:', current_price, 'P0:', start_price, 'sell_level:', sell_level, 'target_pct:', target_pct)

class DummyWS:
    def __init__(self, bids=None, asks=None):
        # default bids set to cover scenario
        self._bids = bids or [['127.92', '0.2'], ['127.66', '1.0'], ['127.65', '1.0'], ['127.60', '5.0']]
        self._asks = asks or [['126.93', '0.08']]
    def get_data(self, pair):
        last = self._bids[0][0] if self._bids else (self._asks[0][0] if self._asks else '0')
        return {'ticker': {'last': last}, 'orderbook': {'asks': self._asks, 'bids': self._bids}}
    def create_connection(self, pair):
        return None

# Run three variations: (A) insufficient top-level liquidity but cumulative ok, (B) no bids above sell_level, (C) top bid already covers
scenarios = {
    'A_cumulative': [['127.92','0.2'], ['127.66','0.5'], ['127.65','0.4']],
    'B_none_above': [['127.60','5.0'], ['127.55','5.0']],
    'C_top_covers': [['127.92','1.0'], ['127.90','2.0']]
}

for name, bids in scenarios.items():
    print('\n----- SCENARIO:', name, 'bids=', bids)
    ws = DummyWS(bids=bids, asks=[['126.93','0.08']])
    at = AutoTrader(lambda: None, ws, sm)
    at._ensure_cycle_struct('SOL')
    at.cycles['SOL'] = {
        'active': True,
        'active_step': 0,
        'table': [{'step':0, 'rate': start_price, 'breakeven_price': breakeven, 'target_delta_pct': target_pct}],
        'last_buy_price': start_price,
        'start_price': start_price,
        'total_invested_usd': start_price * 0.08,
        'base_volume': 0.08
    }
    calls = []
    def fake_place(*args, **kwargs):
        calls.append((args, kwargs))
        return {'success': True, 'filled': args[3]}
    at._place_limit_order_all_or_nothing = fake_place
    at._try_sell('SOL','USDT', current_price)
    print('attempts:', len(calls))
    if len(calls):
        print('exec_price used:', calls[0][0][4])
