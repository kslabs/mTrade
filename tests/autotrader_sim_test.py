import sys
sys.path.append('..')
# Поправка для Windows-консоли: включим UTF-8 для тестового вывода, чтобы печать эмодзи не падала
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
import time
from autotrader import AutoTrader
from state_manager import get_state_manager

class DummyWS:
    def __init__(self, ticker_last=None, orderbook=None):
        self._data = {}
        if ticker_last is not None:
            self._data['ticker'] = {'last': str(ticker_last)}
        if orderbook is not None:
            self._data['orderbook'] = orderbook
    def get_data(self, pair):
        return self._data
    def create_connection(self, pair):
        print('[DummyWS] subscribed', pair)

class DummyAPI:
    def __init__(self, balances=None):
        self.balances = balances or []
    def get_account_balance(self):
        return self.balances


def api_client_provider_factory(balances=None):
    def provider():
        return DummyAPI(balances)
    return provider


def run_simulation():
    sm = get_state_manager()
    # Ensure permissions for ETH
    sm.set_trading_permission('ETH', True)
    sm.set_auto_trade_enabled(True)
    # prepare breakeven params for ETH (default gives some start volume)
    params = sm.get_breakeven_params('ETH')
    params['start_volume'] = 3.0
    sm.set_breakeven_params('ETH', params)

    # Simulate market price 3000 USDT
    ws = DummyWS(ticker_last=3000.0, orderbook={'asks': [[3000.0, 10.0]], 'bids': [[2999.0, 10.0]]})

    # Simulate API with only base balance 0 and quote sufficient
    balances = [{'currency': 'ETH', 'available': '0'}, {'currency': 'USDT', 'available': '10000'}]

    at = AutoTrader(api_client_provider_factory(balances), ws, sm)

    print('\n--- Running _try_start_cycle for ETH ---')
    at._try_start_cycle('ETH', 'USDT', 3000.0)

if __name__ == '__main__':
    run_simulation()
