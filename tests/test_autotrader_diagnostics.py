import os
import time
import tempfile
import json

from autotrader import AutoTrader


class DummyState:
    def get_breakeven_params(self, base):
        return {}


def test_detected_not_overwritten(tmp_path):
    # use a temp diagnostics file
    diag_file = tmp_path / 'diag_test.json'

    at = AutoTrader(api_client_provider=None, ws_manager=None, state_manager=DummyState())
    at._diag_state_file = str(diag_file)

    # ensure fresh
    if os.path.exists(at._diag_state_file):
        os.remove(at._diag_state_file)

    sell_payload = {'decision': 'sell_detected', 'timestamp': time.time(), 'reason': 'price_reached'}
    at._set_last_diagnostic('ADA', sell_payload)

    # now a buy-related diagnostic with decision 'none' should not erase last_detected.sell
    none_payload = {'decision': 'none', 'timestamp': time.time(), 'reason': 'some buy none'}
    at._set_last_diagnostic('ADA', none_payload)

    # read memory
    rec = at.last_diagnostics.get('ADA')
    assert rec is not None
    assert 'last_detected' in rec and 'sell' in rec['last_detected']
    assert rec['last_detected']['sell']['reason'] == 'price_reached'
    assert rec.get('last_decision') is not None
    assert rec['last_decision']['reason'] == 'some buy none'


def test_diagnostics_persist_and_load(tmp_path):
    diag_file = tmp_path / 'diag_test2.json'

    at = AutoTrader(api_client_provider=None, ws_manager=None, state_manager=DummyState())
    at._diag_state_file = str(diag_file)

    # write a detected event
    payload = {'decision': 'sell_detected', 'timestamp': time.time(), 'reason': 'persist_test'}
    at._set_last_diagnostic('ADA', payload)

    # ensure file exists
    assert os.path.exists(at._diag_state_file)

    # create a fresh instance and load
    at2 = AutoTrader(api_client_provider=None, ws_manager=None, state_manager=DummyState())
    at2._diag_state_file = str(diag_file)
    # load explicitly
    at2._load_diagnostics_state()

    rec = at2.last_diagnostics.get('ADA')
    assert rec is not None
    assert 'last_detected' in rec and 'sell' in rec['last_detected']
    assert rec['last_detected']['sell']['reason'] == 'persist_test'
