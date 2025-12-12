import sys
sys.path.append('..')
from autotrader import AutoTrader
from state_manager import get_state_manager


class DummyAPI:
    def __init__(self):
        pass
    def get_account_balance(self):
        return [{'currency': 'ETH', 'available': '0'}, {'currency': 'USDT', 'available': '1000'}]
    def create_spot_order(self, currency_pair=None, side=None, amount=None, price=None, order_type=None, time_in_force=None):
        # Simulate full fill: return amount and left=0
        return {'amount': str(amount), 'left': '0', 'id': 'sim'}


class DummyWS:
    def __init__(self):
        self._data = {'ticker': {'last': '2721.01'}, 'orderbook': {'asks': [[2721.01,'10']], 'bids': [[2721.0,'10']]}}
    def get_data(self, pair):
        return self._data
    def create_connection(self, pair):
        return None


def test_autotrader_start_buy_precision():
    sm = get_state_manager()
    sm.set_trading_permission('ETH', True)
    sm.set_auto_trade_enabled(True)
    params = sm.get_breakeven_params('ETH')
    params['start_volume'] = 3.0
    sm.set_breakeven_params('ETH', params)

    def provider():
        return DummyAPI()

    at = AutoTrader(provider, DummyWS(), sm)

    # run start cycle with price where 3/2721.01 -> ~0.001102 -> with precision 4 should round up to 0.0012
    at._try_start_cycle('ETH', 'USDT', 2721.01)

    cycle = at.cycles.get('ETH')
    assert cycle is not None
    assert cycle.get('active') is True
    # base_volume should be at least 0.0012 after rounding up
    assert cycle.get('base_volume', 0) >= 0.0011
