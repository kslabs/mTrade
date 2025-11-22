import sys
import json
sys.path.append('..')

from mTrade import app, get_pair_info


def test_repo_minimums_used():
    # используем несуществующую котируемую валюту, чтобы API биржи не вернул min-значения
    base = 'ETH'
    quote = 'FOO'
    path = f'/api/pair/info?base_currency={base}&quote_currency={quote}&force=1&debug=1'
    with app.test_request_context(path):
        resp = get_pair_info()
        j = resp.get_json()
        assert j['success'] is True
        data = j.get('data') or {}
        # Ожидаем, что min_base_amount пришёл из pair_minimums.json (0.001)
        assert data.get('min_base_amount') is not None
        # Проверим, что оно совпадает с нашим репозиторием
        assert str(data.get('min_base_amount')) in ('0.001', '0.0010')


if __name__ == '__main__':
    print('Running local test...')
    test_repo_minimums_used()
    print('OK')
