import sys
sys.path.append('..')
from autotrader import AutoTrader
from state_manager import get_state_manager


class DummyAPIFailFOKThenIOC:
    def __init__(self):
        self.calls = []

    def get_account_balance(self):
        return [{'currency': 'ETH', 'available': '0'}, {'currency': 'USDT', 'available': '1000'}]

    def create_spot_order(self, currency_pair=None, side=None, amount=None, price=None, order_type=None, time_in_force=None):
        self.calls.append(time_in_force)
        if (time_in_force or '').lower() == 'fok':
            return {'label': 'FOK_NOT_FILL', 'message': 'Order cannot be filled completely'}
        # Simulate IOC fills fully
        return {'amount': str(amount), 'left': '0', 'id': 'sim_ioc'}


class DummyWS:
    def get_data(self, pair):
        return {'ticker': {'last': '2719.58'}, 'orderbook': {'asks': [['2719.58','20']], 'bids': [['2719.57','10']]}}

    def create_connection(self, pair):
        return None


def test_fok_ioc_fallback():
    sm = get_state_manager()
    sm.set_trading_permission('ETH', True)
    sm.set_auto_trade_enabled(True)
    params = sm.get_breakeven_params('ETH')
    params['start_volume'] = 10.0
    sm.set_breakeven_params('ETH', params)

    def provider():
        return DummyAPIFailFOKThenIOC()

    at = AutoTrader(provider, DummyWS(), sm)

    # Try to place order: first FOK should fail, then IOC should succeed
    res = at._place_limit_order_all_or_nothing('buy', 'ETH', 'USDT', 0.0037, 2719.58)

    assert res.get('success') is True
    assert res.get('tif') == 'ioc'
    assert res.get('filled') >= 0.0037 * 0.999
