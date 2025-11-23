import sys
import json
import os
sys.path.append('..')
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from autotrader import AutoTrader
from state_manager import get_state_manager


class DummyAPIZero:
    def get_account_balance(self):
        return [{'currency': 'ETH', 'available': '0'}, {'currency': 'USDT', 'available': '0'}]


def write_cycles_file(tmp_path, content):
    p = os.path.join(os.getcwd(), 'autotrader_cycles_state.json')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(content, f, indent=2)
    return p


def test_restore_marks_inconsistent_active_cycle_inactive():
    # Prepare a saved state with ETH active and some base_volume
    import time

    saved = {
        'ETH': {
            'active': True,
            'active_step': 0,
            'last_buy_price': 2000.0,
            'start_price': 2000.0,
            'total_invested_usd': 10.0,
            'base_volume': 0.005,
            'saved_at': time.time()
        }
    }

    write_cycles_file('.', saved)

    sm = get_state_manager()

    def provider():
        return DummyAPIZero()

    at = AutoTrader(provider, None, sm)

    # After loading, since account has 0 ETH, the saved active cycle should be marked inactive
    assert at.cycles.get('ETH') is not None
    assert at.cycles['ETH'].get('active') is False


if __name__ == '__main__':
    test_restore_marks_inconsistent_active_cycle_inactive()
    print('OK')
