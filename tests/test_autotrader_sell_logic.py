import sys
import os

# Make sure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from autotrader import AutoTrader
from state_manager import get_state_manager


class DummyWS:
    def __init__(self, bids=None):
        # bids: list of [price, amount]
        self._bids = bids or [['100.00', '1']]

    def get_data(self, pair):
        # ticker last = bid price
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


def test_no_sell_if_price_below_target():
    sm = get_state_manager()
    sm.set_trading_permission('TEST', True)
    sm.set_auto_trade_enabled(True)

    # dummy API client provider - not used because we patch _place_limit_order
    def provider():
        return None

    at = AutoTrader(provider, DummyWS(), sm)

    # configure cycle: breakeven 100, target 0.5% => sell_level = 100.5
    setup_cycle(at, 'TEST', 100.0, 0.5, 1.0)

    calls = []

    # patch placing method to record calls
    def fake_place(*args, **kwargs):
        calls.append((args, kwargs))
        return {'success': True, 'filled': args[3]}

    at._place_limit_order_all_or_nothing = fake_place

    # current_price = 100.05 (< 100.5) - should NOT trigger sell
    at._try_sell('TEST', 'USDT', 100.05)

    assert calls == [], "_place_limit_order_all_or_nothing should not be called when price < target sell level"


def test_sell_requires_orderbook_liquidity():
    sm = get_state_manager()
    sm.set_trading_permission('TEST', True)
    sm.set_auto_trade_enabled(True)

    # orderbook with low liquidity on level 1
    ws_low = DummyWS(bids=[['100.60', '0.1']])
    at = AutoTrader(lambda: None, ws_low, sm)
    setup_cycle(at, 'TEST', 100.0, 0.5, 1.0)  # sell_level = 100.5

    calls = []
    def fake_place(*args, **kwargs):
        calls.append((args, kwargs))
        return {'success': True, 'filled': args[3]}

    at._place_limit_order_all_or_nothing = fake_place

    # current_price meets target (>=100.5), but bids amount insufficient -> do NOT attempt sell (all-or-nothing)
    at._try_sell('TEST', 'USDT', 100.6)
    assert len(calls) == 0, "Should NOT attempt sell when bids liquidity is insufficient (all-or-nothing)"

    # Now update WS with sufficient liquidity
    at.ws_manager = DummyWS(bids=[['100.60', '1.5']])
    # Ensure orderbook updated (no debug prints)
    _ = at._get_orderbook('TEST', 'USDT')
    at._try_sell('TEST', 'USDT', 100.6)
    assert len(calls) == 1, "Should attempt sell when bids liquidity is sufficient and price >= sell_level"


def test_fractional_orderbook_level_triggers_sell():
    sm = get_state_manager()
    sm.set_trading_permission('FRAC', True)
    sm.set_auto_trade_enabled(True)

    # set fractional orderbook_level = 0.5 (50% depth)
    params = sm.get_breakeven_params('FRAC')
    params['orderbook_level'] = 0.5
    sm.set_breakeven_params('FRAC', params)

    # orderbook bids with 4 levels -> level = ceil(4*0.5) = 2
    ws = DummyWS(bids=[['100.60', '0.1'], ['100.55', '2.0'], ['100.50', '5.0']])
    at = AutoTrader(lambda: None, ws, sm)
    setup_cycle(at, 'FRAC', 100.0, 0.5, 1.0)  # sell_level = 100.5, base_volume=1.0

    calls = []
    def fake_place(*args, **kwargs):
        calls.append((args, kwargs))
        return {'success': True, 'filled': args[3]}

    at._place_limit_order_all_or_nothing = fake_place

    # current price 100.6 >= sell_level and bids at level 2 have amount 2.0 >= base_volume
    at._try_sell('FRAC', 'USDT', 100.6)
    assert len(calls) == 1, "Should attempt sell when fractional orderbook_level points to a sufficiently liquid level"


def test_combined_bids_allow_sell():
    sm = get_state_manager()
    sm.set_trading_permission('COMB', True)
    sm.set_auto_trade_enabled(True)

    # sell_level = 100.5, base_volume=1.0
    setup_cycle_for_comb = lambda at: setup_cycle(at, 'COMB', 100.0, 0.5, 1.0)

    # Bids split across two price levels both >= sell_level → individually insufficient, cumulatively enough
    ws = DummyWS(bids=[['100.60', '0.4'], ['100.55', '0.6'], ['100.50', '10']])
    at = AutoTrader(lambda: None, ws, sm)
    setup_cycle_for_comb(at)

    calls = []

    def fake_place(*args, **kwargs):
        calls.append((args, kwargs))
        return {'success': True, 'filled': args[3]}

    at._place_limit_order_all_or_nothing = fake_place

    # current_price meets sell_level and cumulative bids at >= sell_level cover base_volume -> should sell
    at._try_sell('COMB', 'USDT', 100.6)
    assert len(calls) == 1, "Should attempt sell when cumulative bids at or above sell_level cover required volume"


def test_exec_price_uses_lowest_eligible_bid_when_current_price_above():
    sm = get_state_manager()
    sm.set_trading_permission('CUR', True)
    sm.set_auto_trade_enabled(True)

    # bids at 100.60 and 100.55 -> cumulative covers 1.0
    ws = DummyWS(bids=[['100.60', '0.4'], ['100.55', '0.6'], ['100.50', '10']])
    at = AutoTrader(lambda: None, ws, sm)
    setup_cycle(at, 'CUR', 100.0, 0.5, 1.0)  # sell_level = 100.5

    calls = []

    def fake_place(*args, **kwargs):
        calls.append((args, kwargs))
        return {'success': True, 'filled': args[3]}

    at._place_limit_order_all_or_nothing = fake_place

    # current_price is higher than any bid -> previous code failed because it used current_price as limit
    at._try_sell('CUR', 'USDT', 101.0)

    assert len(calls) == 1, "Should attempt sell when cumulative bids cover base_volume even if current_price > bids"
    # Ensure the order price used was the lowest eligible bid (100.50) so the FOK can be matched
    assert abs(float(calls[0][0][4]) - 100.50) < 1e-8, f"Expected exec price 100.50, got {calls[0][0][4]}"


def test_use_top_bid_when_current_price_above_and_no_eligible_bids_but_profitable():
    sm = get_state_manager()
    sm.set_trading_permission('TB1', True)
    sm.set_auto_trade_enabled(True)

    # Create a table where sell_level is moderate but current_price is high
    # last_buy_price low enough so selling at top bid is still profitable
    ws = DummyWS(bids=[['99.50', '2.0'], ['99.00', '2.0']])
    at = AutoTrader(lambda: None, ws, sm)
    # setup cycle such that last_buy_price=50, base_volume=2.0 and breakeven=100 so eligible_bids will be empty
    at._ensure_cycle_struct('TB1')
    at.cycles['TB1'] = {
        'active': True,
        'active_step': 0,
        'table': [{'step': 0, 'rate': 100.0, 'breakeven_price': 100.0, 'target_delta_pct': 0.0}],
        'last_buy_price': 50.0,
        'start_price': 50.0,
        'total_invested_usd': 100.0,
        'base_volume': 2.0
    }

    calls = []

    def fake_place(*args, **kwargs):
        calls.append((args, kwargs))
        return {'success': True, 'filled': args[3]}

    at._place_limit_order_all_or_nothing = fake_place

    # current_price above sell_level and top bid has enough amount to fill -> should use top bid
    at._try_sell('TB1', 'USDT', 110.0)

    assert len(calls) == 1, 'Should attempt sell when top bid is profitable and price >= sell_level even if bids < current_price'
    # ensure exec_price chosen equals top bid price (99.50)
    assert abs(float(calls[0][0][4]) - 99.50) < 1e-8


def test_level_parameter_deeper_than_book_should_not_block_sell():
    sm = get_state_manager()
    sm.set_trading_permission('DEEP', True)
    sm.set_auto_trade_enabled(True)

    # orderbook has 2 bids only; parameter asks for level=10 -> should be clamped and we still attempt to sell
    ws = DummyWS(bids=[['200.0', '0.4'], ['199.5', '1.0']])
    at = AutoTrader(lambda: None, ws, sm)

    params = sm.get_breakeven_params('DEEP')
    params['orderbook_level'] = 10  # deeper than available bids
    sm.set_breakeven_params('DEEP', params)

    setup_cycle(at, 'DEEP', 199.0, 0.5, 1.0)

    calls = []

    def fake_place(*args, **kwargs):
        calls.append((args, kwargs))
        return {'success': True, 'filled': args[3]}

    at._place_limit_order_all_or_nothing = fake_place

    # current price higher so sell_level reached; should not early return due to level depth
    at._try_sell('DEEP', 'USDT', 200.5)

    assert len(calls) == 1, "Should still attempt sell even when requested orderbook_level deeper than available depth"


def test_fallback_aggregate_bids_when_no_eligible_bids_profitable():
    sm = get_state_manager()
    sm.set_trading_permission('FBP', True)
    sm.set_auto_trade_enabled(True)

    # sell_level = 100.5 but bids below this level; aggregated they still cover base_volume at price 100.45
    bids = [['100.49', '0.4'], ['100.46', '0.4'], ['100.45', '0.3']]
    ws = DummyWS(bids=bids)
    at = AutoTrader(lambda: None, ws, sm)
    setup_cycle(at, 'FBP', 100.0, 0.5, 1.0)  # base_volume=1.0, avg_invest_price ~100

    calls = []

    def fake_place(*args, **kwargs):
        calls.append((args, kwargs))
        return {'success': True, 'filled': args[3]}

    at._place_limit_order_all_or_nothing = fake_place

    at._try_sell('FBP', 'USDT', 100.6)
    assert len(calls) == 1
    # because aggregated fallback price should be the deepest price required (100.45)
    assert abs(float(calls[0][0][4]) - 100.45) < 1e-8


def test_fallback_aggregate_bids_unprofitable():
    sm = get_state_manager()
    sm.set_trading_permission('FBU', True)
    sm.set_auto_trade_enabled(True)

    # sell_level = 100.5 but aggregated bids only available at 99.0 which is loss against avg_invest ~100
    bids = [['100.10', '0.2'], ['99.50', '0.3'], ['99.00', '1.0']]
    ws = DummyWS(bids=bids)
    at = AutoTrader(lambda: None, ws, sm)
    setup_cycle(at, 'FBU', 100.0, 0.5, 1.0)  # buy price ~100

    calls = []

    def fake_place(*args, **kwargs):
        calls.append((args, kwargs))
        return {'success': True, 'filled': args[3]}

    at._place_limit_order_all_or_nothing = fake_place

    at._try_sell('FBU', 'USDT', 100.6)
    assert len(calls) == 0, "Should not sell when only aggregated fallback results in a loss"

def test_sell_external_holdings_triggers_sell():
        sm = get_state_manager()
        sm.set_trading_permission('LINK', True)
        sm.set_auto_trade_enabled(True)

        # ensure target_pct doesn't require extra growth — make sell level equal to breakeven
        p = sm.get_breakeven_params('LINK') or {}
        # calculate_breakeven_table uses 'pprof' to compute target_delta_pct for step 0
        p['pprof'] = 0.0
        sm.set_breakeven_params('LINK', p)

        # API client exposes account balance with LINK holdings
        class DummyAPI:
            def get_account_balance(self):
                return [{'currency': 'LINK', 'available': '2.0'}]

        # orderbook bids sufficient to cover holdings (bids must be >= sell_level)
        ws = DummyWS(bids=[['13.10', '2.0'], ['13.05', '5.0']])
        at = AutoTrader(lambda: DummyAPI(), ws, sm)

        calls = []

        def fake_place(*args, **kwargs):
            calls.append((args, kwargs))
            return {'success': True, 'filled': args[3]}

        at._place_limit_order_all_or_nothing = fake_place

        # No cycle for LINK, but holdings exist and current price above sell level
        # Use a price higher than typical computed sell_level to ensure sell attempt
        # set a price above typical computed sell_level (target_delta_pct ~0.57%)
        at._try_sell('LINK', 'USDT', 13.00)

        assert len(calls) == 1, 'Should attempt sell when external holdings exist and price >= sell level'

def test_sell_external_holdings_insufficient_liquidity():
        sm = get_state_manager()
        sm.set_trading_permission('LINK', True)
        sm.set_auto_trade_enabled(True)

        class DummyAPI:
            def get_account_balance(self):
                return [{'currency': 'LINK', 'available': '2.0'}]

        # orderbook bids insufficient (only 0.5 available at >= sell_level)
        ws = DummyWS(bids=[['12.04', '0.2'], ['12.03', '0.3'], ['12.00', '10.0']])
        at = AutoTrader(lambda: DummyAPI(), ws, sm)

        calls = []

        def fake_place(*args, **kwargs):
            calls.append((args, kwargs))
            return {'success': True, 'filled': args[3]}

        at._place_limit_order_all_or_nothing = fake_place

        at._try_sell('LINK', 'USDT', 12.088)

        # With all-or-nothing semantics, insufficient bids should not trigger a sell
        assert len(calls) == 0, 'Should NOT attempt sell when external holdings present but bids liquidity insufficient (all-or-nothing)'


def test_doge_sell_with_active_cycle():
    sm = get_state_manager()
    sm.set_trading_permission('DOGE', True)
    sm.set_auto_trade_enabled(True)

    # orderbook bids sufficient to cover base_volume
    ws = DummyWS(bids=[['0.160', '2.0'], ['0.155', '10.0']])
    at = AutoTrader(lambda: None, ws, sm)
    # setup a small DOGE cycle where breakeven=0.155 and target 0.5% -> sell_level ~0.155775
    setup_cycle(at, 'DOGE', 0.155, 0.5, 1.0)

    calls = []

    def fake_place(*args, **kwargs):
        calls.append((args, kwargs))
        return {'success': True, 'filled': args[3]}

    at._place_limit_order_all_or_nothing = fake_place

    # current price 0.16 >= sell_level -> should attempt sell
    at._try_sell('DOGE', 'USDT', 0.17)

    assert len(calls) == 1, 'DOGE active cycle should attempt sell when price >= sell level'


def test_doge_sell_external_holdings_triggers_sell():
    sm = get_state_manager()
    sm.set_trading_permission('DOGE', True)
    sm.set_auto_trade_enabled(True)

    # API client exposes account balance with DOGE holdings
    class DummyAPI:
        def get_account_balance(self):
            return [{'currency': 'DOGE', 'available': '100.0'}]

    # orderbook bids sufficient to cover holdings (include price >= target sell)
    ws = DummyWS(bids=[['0.170', '100.0'], ['0.165', '500.0']])
    at = AutoTrader(lambda: DummyAPI(), ws, sm)

    calls = []

    def fake_place(*args, **kwargs):
        calls.append((args, kwargs))
        return {'success': True, 'filled': args[3]}

    at._place_limit_order_all_or_nothing = fake_place

    # ensure target_pct doesn't block immediate sell for temporary cycle
    params = sm.get_breakeven_params('DOGE') or {}
    params['pprof'] = 0.0
    sm.set_breakeven_params('DOGE', params)

    # orderbook bids sufficient to cover holdings at or above sell level
    # No cycle for DOGE, but holdings exist and we call with price >= breakeven
    at._try_sell('DOGE', 'USDT', 0.17)

    assert len(calls) == 1, 'Should attempt sell for external DOGE holdings when liquidity and price permit'
